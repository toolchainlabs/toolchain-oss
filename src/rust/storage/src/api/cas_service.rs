// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::convert::TryInto;
use std::sync::Arc;

use bytes::{BufMut, Bytes, BytesMut};
use digest::Digest;
use futures::{future, StreamExt};
use tonic::{Request, Response, Status};

use protos::build::bazel::remote::execution::v2::{
    batch_read_blobs_response, batch_update_blobs_response,
    content_addressable_storage_server::ContentAddressableStorage, BatchReadBlobsRequest,
    BatchReadBlobsResponse, BatchUpdateBlobsRequest, BatchUpdateBlobsResponse, Digest as ApiDigest,
    FindMissingBlobsRequest, FindMissingBlobsResponse, GetTreeRequest, GetTreeResponse,
};

use crate::api::{convert_digests, InnerServer};
use crate::driver::{DriverState, Instance, StreamingWriteError};

pub(super) struct CasService {
    pub(super) inner: Arc<InnerServer>,
}

impl CasService {
    /// Reads a single blob out of a `BlobStorage` and consolidates all chunks into a single
    /// `Bytes`. Returns the response struct used by the `batch_read_blobs` RPC implementation.
    async fn read_blob(
        &self,
        instance: &Instance,
        api_digest: ApiDigest,
    ) -> batch_read_blobs_response::Response {
        fn make_response(
            digest: ApiDigest,
            code: protos::google::rpc::Code,
            message: impl Into<String>,
        ) -> batch_read_blobs_response::Response {
            batch_read_blobs_response::Response {
                digest: Some(digest),
                data: Bytes::default(),
                status: Some(protos::google::rpc::Status {
                    code: code as i32,
                    message: message.into(),
                    ..protos::google::rpc::Status::default()
                }),
            }
        }

        // Convert the Digest proto into the internal Digest struct.
        let digest: Digest = match api_digest.clone().try_into() {
            Ok(digest) => digest,
            Err(_) => {
                return make_response(
                    api_digest,
                    protos::google::rpc::Code::InvalidArgument,
                    "Invalid digest",
                );
            }
        };

        // Obtain a stream of data chunks for this blob.
        let mut buffer = BytesMut::with_capacity(digest.size_bytes);
        let mut stream = match self
            .inner
            .cas
            .read_blob(
                instance.clone(),
                digest,
                2048,
                None,
                None,
                DriverState::default(),
            )
            .await
        {
            Ok(Some(stream)) => stream,
            Ok(None) => {
                return make_response(api_digest, protos::google::rpc::Code::NotFound, "");
            }
            Err(err) => {
                return make_response(api_digest, protos::google::rpc::Code::Internal, err);
            }
        };

        // Obtain each data chunk and append it to the consolidated buffer.
        while let Some(chunk) = stream.next().await {
            let chunk = match chunk {
                Ok(c) => c,
                Err(err) => {
                    return make_response(api_digest, protos::google::rpc::Code::Internal, err)
                }
            };
            buffer.put_slice(&chunk[..]);
        }

        // Ensure that the buffer length matches the expected length.
        if buffer.len() != digest.size_bytes {
            return make_response(
                api_digest,
                protos::google::rpc::Code::DataLoss,
                format!(
                    "digest has wrong size (expected={}, actual={})",
                    digest.size_bytes,
                    buffer.len()
                ),
            );
        }

        batch_read_blobs_response::Response {
            digest: Some(api_digest),
            data: buffer.freeze(),
            status: Some(protos::google::rpc::Status {
                code: protos::google::rpc::Code::Ok as i32,
                ..protos::google::rpc::Status::default()
            }),
        }
    }

    /// Write a single blob into a `BlobStorage` given a `Bytes` with the entire content.
    /// (This is used by `batch_update_blobs`.)
    async fn write_blob(
        &self,
        instance: &Instance,
        api_digest_opt: Option<ApiDigest>,
        data: Bytes,
    ) -> batch_update_blobs_response::Response {
        fn make_response(
            digest: Option<ApiDigest>,
            code: protos::google::rpc::Code,
            message: impl Into<String>,
        ) -> batch_update_blobs_response::Response {
            batch_update_blobs_response::Response {
                digest,
                status: Some(protos::google::rpc::Status {
                    code: code as i32,
                    message: message.into(),
                    ..protos::google::rpc::Status::default()
                }),
            }
        }

        // Extract the API-form of the digest from the request proto.
        let api_digest = match api_digest_opt.clone() {
            Some(api_digest) => api_digest,
            None => {
                return make_response(
                    api_digest_opt,
                    protos::google::rpc::Code::InvalidArgument,
                    "Missing digest",
                );
            }
        };

        // Convert that digest into the internal Digest struct.
        let digest: Digest = match api_digest.try_into() {
            Ok(digest) => digest,
            Err(_) => {
                return make_response(
                    api_digest_opt,
                    protos::google::rpc::Code::InvalidArgument,
                    "Invalid digest",
                );
            }
        };

        let write = async move {
            let mut attempt = self
                .inner
                .cas
                .begin_write_blob(instance.clone(), digest, DriverState::default())
                .await?;

            attempt.write(data).await?;
            attempt.commit().await
        };

        let write_result = write
            .await
            .or_else(StreamingWriteError::ok_if_already_exists);

        match write_result {
            Ok(()) => make_response(api_digest_opt, protos::google::rpc::Code::Ok, ""),
            Err(e) => make_response(api_digest_opt, protos::google::rpc::Code::Internal, e),
        }
    }
}

#[tonic::async_trait]
impl ContentAddressableStorage for CasService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn find_missing_blobs(
        &self,
        request: Request<FindMissingBlobsRequest>,
    ) -> Result<Response<FindMissingBlobsResponse>, Status> {
        let request = request.into_inner();
        let instance = Instance {
            name: request.instance_name,
        };
        let digests = convert_digests(request.blob_digests)?;
        let missing_digests = self
            .inner
            .cas
            .find_missing_blobs(instance, digests, DriverState::default())
            .await
            .map_err(Status::internal)?;
        let response = FindMissingBlobsResponse {
            missing_blob_digests: missing_digests.into_iter().map(|d| d.into()).collect(),
        };
        Ok(Response::new(response))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn batch_update_blobs(
        &self,
        request: Request<BatchUpdateBlobsRequest>,
    ) -> Result<Response<BatchUpdateBlobsResponse>, Status> {
        let request = request.into_inner();
        let instance = Instance {
            name: request.instance_name,
        };

        let write_requests_futures: Vec<_> = request
            .requests
            .into_iter()
            .map(|req| self.write_blob(&instance, req.digest, req.data))
            .collect();

        let responses = future::join_all(write_requests_futures).await;

        Ok(Response::new(BatchUpdateBlobsResponse { responses }))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn batch_read_blobs(
        &self,
        request: Request<BatchReadBlobsRequest>,
    ) -> Result<Response<BatchReadBlobsResponse>, Status> {
        let request = request.into_inner();
        let instance = Instance {
            name: request.instance_name,
        };

        let read_futures: Vec<_> = request
            .digests
            .into_iter()
            .map(|digest| self.read_blob(&instance, digest))
            .collect();

        let responses = future::join_all(read_futures).await;

        Ok(Response::new(BatchReadBlobsResponse { responses }))
    }

    type GetTreeStream = tonic::Streaming<GetTreeResponse>;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_tree(
        &self,
        _request: Request<GetTreeRequest>,
    ) -> Result<Response<Self::GetTreeStream>, Status> {
        Err(Status::unimplemented("TBD"))
    }
}
