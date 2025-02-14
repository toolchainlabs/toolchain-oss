// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::HashSet;
use std::convert::TryInto;
use std::sync::Arc;
use std::time::Instant;

use bytes::{BufMut, Bytes, BytesMut};
use digest::{required_digest, Digest};
use futures::{future, future::BoxFuture, FutureExt, StreamExt};
use prost::Message;
use protos::build::bazel::remote::execution::v2::{
    action_cache_server::ActionCache, ActionResult, Digest as ApiDigest, GetActionResultRequest,
    Tree, UpdateActionResultRequest,
};
use rand::RngCore;
use tonic::{Request, Response, Status};

use crate::api::InnerServer;
use crate::driver::{BlobStorage, DriverState, Instance, StorageError, StreamingWriteError};

pub(super) struct ActionCacheService {
    pub(super) inner: Arc<InnerServer>,
}

impl ActionCacheService {
    fn require_digest(api_digest_opt: Option<&ApiDigest>) -> Result<Digest, StorageError> {
        let api_digest =
            api_digest_opt.ok_or_else(|| StorageError::Internal("Missing digest".into()))?;
        api_digest.clone().try_into().map_err(|err| {
            StorageError::Internal(format!(
                "invalid digest {}/{}: {}",
                api_digest.hash, api_digest.size_bytes, err
            ))
        })
    }

    async fn expand_tree_to_digests(
        &self,
        instance: Instance,
        api_tree_digest: &ApiDigest,
    ) -> Result<Option<HashSet<Digest>>, StorageError> {
        let tree_digest: Digest = api_tree_digest.clone().try_into().map_err(|err| {
            StorageError::Internal(format!(
                "invalid digest {}/{}: {}",
                api_tree_digest.hash, api_tree_digest.size_bytes, err
            ))
        })?;

        let mut stream = match self
            .inner
            .cas
            .read_blob(
                instance,
                tree_digest,
                16 * 1024 * 1024,
                None,
                None,
                DriverState::default(),
            )
            .await?
        {
            Some(s) => s,
            None => return Ok(None),
        };

        let mut buffer = BytesMut::with_capacity(tree_digest.size_bytes);
        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            buffer.put_slice(&chunk[..]);
        }

        let mut digests = HashSet::new();

        let tree = Tree::decode(buffer.freeze())
            .map_err(|_| StorageError::Internal("tree decode error".into()))?;

        if let Some(root) = &tree.root {
            for file_node in &root.files {
                digests.insert(Self::require_digest(file_node.digest.as_ref())?);
            }
        }
        for directory in &tree.children {
            for file_node in &directory.files {
                digests.insert(Self::require_digest(file_node.digest.as_ref())?);
            }
        }

        Ok(Some(digests))
    }

    async fn is_action_result_complete(
        &self,
        instance: Instance,
        action_result: &ActionResult,
    ) -> Result<bool, StorageError> {
        let digests = {
            let mut digests = HashSet::new();

            if let Some(ref digest) = action_result.stdout_digest {
                digests.insert(Self::require_digest(Some(digest))?);
            }
            if let Some(ref digest) = action_result.stderr_digest {
                digests.insert(Self::require_digest(Some(digest))?);
            }

            for output_file in &action_result.output_files {
                digests.insert(Self::require_digest(output_file.digest.as_ref())?);
            }

            let tree_digest_sets_futs = action_result
                .output_directories
                .iter()
                .flat_map(|dir| dir.tree_digest.as_ref())
                .map(|api_digest| self.expand_tree_to_digests(instance.clone(), api_digest))
                .collect::<Vec<_>>();

            let tree_digest_sets = futures::future::try_join_all(tree_digest_sets_futs).await?;
            for tree_digest_set_opt in tree_digest_sets {
                match tree_digest_set_opt {
                    Some(tree_digest_set) => digests.extend(tree_digest_set),
                    None => return Ok(false),
                }
            }

            digests.into_iter().collect::<Vec<_>>()
        };

        let missing_digests = self
            .inner
            .cas
            .find_missing_blobs(instance, digests, DriverState::default())
            .await?;
        Ok(missing_digests.is_empty())
    }
}

#[tonic::async_trait]
impl ActionCache for ActionCacheService {
    /// Retrieve the action result from BlobStorage. Returns NOT_FOUND error if the Action's
    /// digest does not have an associated ActionResult.
    ///
    /// TODO: Support `inline_output_files`, `inline_stdout`, and `inline_stderr`.
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_action_result(
        &self,
        request: Request<GetActionResultRequest>,
    ) -> Result<Response<ActionResult>, Status> {
        let request = request.into_inner();
        let instance = Instance {
            name: request.instance_name,
        };

        let action_digest = required_digest("action_digest", request.action_digest)
            .map_err(Status::invalid_argument)?;

        let stream_opt = self
            .inner
            .action_cache
            .read_blob(
                instance.clone(),
                action_digest,
                16 * 1024 * 1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .map_err(Status::internal)?;

        let mut stream = match stream_opt {
            Some(s) => s,
            None => return Err(Status::not_found("Not found")),
        };

        let mut buffer = BytesMut::new();
        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            buffer.put_slice(&chunk[..]);
        }

        let mut action_result = match ActionResult::decode(buffer.freeze()) {
            Ok(ar) => ar,
            Err(err) => {
                log::error!(
                    "Failed to decode ActionResult for digest {:?}: {:?}",
                    &action_digest,
                    err
                );
                return Err(Status::data_loss(
                    "Failed to decode ActionResult from storage",
                ));
            }
        };

        // Check whether all digests associated with this ActionResult are present in the CAS.
        if self.inner.check_action_cache_completeness {
            let choice = rand::thread_rng().next_u32() % 1000;
            if choice < self.inner.completeness_check_probability {
                let completeness_check_start = Instant::now();
                let action_result_complete = self
                    .is_action_result_complete(instance.clone(), &action_result)
                    .await?;

                metrics::histogram!(
                    "toolchain_storage_completeness_check_seconds",
                    completeness_check_start.elapsed(),
                    "complete" => if action_result_complete { "true".to_owned() } else { "false".to_owned() },
                );
                if !action_result_complete {
                    return Err(Status::not_found("Not found"));
                }
            }
        }

        // Helper function for reading blobs to inline into the ActionResult.
        fn read_blob(
            api_digest_opt: Option<ApiDigest>,
            instance: Instance,
            cas: Arc<dyn BlobStorage + Send + Sync + 'static>,
            batch_api_limit: usize,
        ) -> BoxFuture<'static, Option<Bytes>> {
            let api_digest = match api_digest_opt {
                Some(d) => d,
                None => return future::ready(None).boxed(),
            };

            let digest: Digest = match api_digest.try_into() {
                Ok(d) => d,
                Err(_) => return future::ready(None).boxed(),
            };

            if digest.size_bytes < 1 && (digest.size_bytes) > batch_api_limit {
                return future::ready(None).boxed();
            }

            async move {
                let stream_opt = cas
                    .read_blob(
                        instance,
                        digest,
                        16 * 1024 * 1024,
                        None,
                        None,
                        DriverState::default(),
                    )
                    .await
                    .ok()?;

                let mut stream = stream_opt?;

                let mut buffer = BytesMut::with_capacity(digest.size_bytes);
                while let Some(chunk) = stream.next().await {
                    let chunk = chunk.ok()?;
                    buffer.put_slice(&chunk[..]);
                }

                Some(buffer.freeze())
            }
            .boxed()
        }

        let stdout_fut_opt = if request.inline_stdout {
            let instance = instance.clone();
            read_blob(
                action_result.stdout_digest.clone(),
                instance,
                self.inner.cas.clone(),
                self.inner.max_batch_total_size_bytes,
            )
            .boxed()
        } else {
            future::ready(None).boxed()
        };

        let stderr_fut_opt = if request.inline_stderr {
            let instance = instance.clone();
            read_blob(
                action_result.stderr_digest.clone(),
                instance,
                self.inner.cas.clone(),
                self.inner.max_batch_total_size_bytes,
            )
            .boxed()
        } else {
            future::ready(None).boxed()
        };

        let (stdout_opt_bytes, stderr_opt_bytes) = futures::join!(stdout_fut_opt, stderr_fut_opt);
        action_result.stdout_raw = stdout_opt_bytes.unwrap_or_default();
        action_result.stderr_raw = stderr_opt_bytes.unwrap_or_default();

        Ok(Response::new(action_result))
    }

    /// Write an action result to BlobStorage.
    ///
    /// Note: The action_digest is used as the key into the BlobStorage. The action_digest
    /// length (which is the length of the encoded Action) is not checked against the length of
    /// the encoded ActionResult which is actually the content written into the BlobStorage.
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn update_action_result(
        &self,
        request: Request<UpdateActionResultRequest>,
    ) -> Result<Response<ActionResult>, Status> {
        let request = request.into_inner();
        let instance = Instance {
            name: request.instance_name,
        };

        let action_digest = required_digest("action_digest", request.action_digest)
            .map_err(Status::invalid_argument)?;

        let mut action_result = request
            .action_result
            .ok_or_else(|| Status::invalid_argument("Missing action_result"))?;

        let mut write_futures = Vec::new();

        // Helper function for writing a single Bytes to storage.
        async fn write_blob(
            storage: Arc<dyn BlobStorage + Send + Sync + 'static>,
            instance: Instance,
            digest: Digest,
            data: Bytes,
        ) -> Result<(), Status> {
            let write = async move {
                let mut attempt = storage
                    .begin_write_blob(instance, digest, DriverState::default())
                    .await?;
                attempt.write(data).await?;
                attempt.commit().await
            };
            write
                .await
                .or_else(StreamingWriteError::ok_if_already_exists)
                .map_err(Status::internal)
        }

        // Write any inline stdout data to the CAS and remove from the action result.
        if !action_result.stdout_raw.is_empty() {
            let stdout_bytes = action_result.stdout_raw.clone();
            let stdout_digest = Digest::of_bytes(&stdout_bytes)
                .map_err(|_| Status::invalid_argument("Failed to hash stdout_raw"))?;

            action_result.stdout_raw.clear();
            action_result.stdout_digest = Some(stdout_digest.into());

            let stdout_write_fut = write_blob(
                self.inner.cas.clone(),
                instance.clone(),
                stdout_digest,
                stdout_bytes,
            );
            write_futures.push(stdout_write_fut);
        }

        // Write any inline stderr data to the CAS and remove from the action result.
        if !action_result.stderr_raw.is_empty() {
            let stderr_bytes = action_result.stderr_raw.clone();
            let stderr_digest = Digest::of_bytes(&stderr_bytes)
                .map_err(|_| Status::invalid_argument("Failed to hash stderr_raw"))?;

            action_result.stderr_raw.clear();
            action_result.stderr_digest = Some(stderr_digest.into());

            let stderr_write_fut = write_blob(
                self.inner.cas.clone(),
                instance.clone(),
                stderr_digest,
                stderr_bytes,
            );
            write_futures.push(stderr_write_fut);
        }

        let mut buffer = BytesMut::with_capacity(action_result.encoded_len());
        action_result
            .encode(&mut buffer)
            .map_err(|_| Status::internal("Failed to encode ActionResult for storage"))?;

        let action_result_write_fut = write_blob(
            self.inner.action_cache.clone(),
            instance,
            action_digest,
            buffer.freeze(),
        );
        write_futures.push(action_result_write_fut);

        futures::future::try_join_all(write_futures).await?;
        Ok(Response::new(action_result))
    }
}
