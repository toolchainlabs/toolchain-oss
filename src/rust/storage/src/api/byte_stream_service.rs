// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::pin::Pin;
use std::sync::Arc;

use digest::Digest;
use futures::{Stream, StreamExt};
use protos::google::bytestream::byte_stream_server::ByteStream;
use protos::google::bytestream::{
    QueryWriteStatusRequest, QueryWriteStatusResponse, ReadRequest, ReadResponse, WriteRequest,
    WriteResponse,
};
use tonic::{Request, Response, Status, Streaming};

use crate::api::sync_wrapper::SyncWrapper;
use crate::api::InnerServer;
use crate::driver::{DriverState, Instance, StorageError, StreamingWriteError};

pub(super) struct ByteStreamService {
    pub(super) inner: Arc<InnerServer>,
}

#[derive(Debug, Eq, PartialEq)]
struct ParsedWriteResourceName<'a> {
    instance_name: &'a str,
    _uuid: &'a str,
    hash: &'a str,
    size: usize,
}

/// Parses a resource name of the form `{instance_name}/uploads/{uuid}/blobs/{hash}/{size}` into
/// a struct with references to the individual components of the resource name. The
/// `{instance_name}` may be blank (with no leading slash).
fn parse_write_resource_name(resource: &str) -> Result<ParsedWriteResourceName<'_>, String> {
    if resource.is_empty() {
        return Err("Missing resource name".to_owned());
    }

    // Parse the resource name into parts separated by slashes (/).
    let parts: Vec<_> = resource.split('/').collect();

    // Search for the `uploads` path component.
    let uploads_index = match parts.iter().position(|p| *p == "uploads") {
        Some(index) => index,
        None => return Err("Malformed resource name: missing `uploads` component".to_owned()),
    };
    let instance_parts = &parts[0..uploads_index];

    if (parts.len() - uploads_index) < 5 {
        return Err(
            "Malformed resource name: not enough path components after `uploads`".to_owned(),
        );
    }

    if parts[uploads_index + 2] != "blobs" {
        return Err("Malformed resource name: expected `blobs` component".to_owned());
    }

    let size = parts[uploads_index + 4]
        .parse::<usize>()
        .map_err(|_| "Malformed resource name: cannot parse size".to_owned())?;

    let instance_name = if instance_parts.is_empty() {
        ""
    } else {
        let last_instance_name_index =
            instance_parts.iter().map(|x| (*x).len()).sum::<usize>() + instance_parts.len() - 1;
        &resource[0..last_instance_name_index]
    };

    Ok(ParsedWriteResourceName {
        instance_name,
        _uuid: parts[uploads_index + 1],
        hash: parts[uploads_index + 3],
        size,
    })
}

#[derive(Debug, Eq, PartialEq)]
struct ParsedReadResourceName<'a> {
    instance_name: &'a str,
    hash: &'a str,
    size: usize,
}

/// Parses a resource name of the form `"{instance_name}/blobs/{hash}/{size}"` into a struct
/// with references to the individual components of the resource name. The `{instance_name}`
/// may be blank (with no leading slash).
fn parse_read_resource_name(resource: &str) -> Result<ParsedReadResourceName<'_>, String> {
    if resource.is_empty() {
        return Err("Missing resource name".to_owned());
    }

    // Parse the resource name into parts separated by slashes (/).
    let parts: Vec<_> = resource.split('/').collect();

    // Search for the `blobs` path component.
    let blobs_index = match parts.iter().position(|p| *p == "blobs") {
        Some(index) => index,
        None => return Err("Malformed resource name: missing `blobs` component".to_owned()),
    };
    let instance_parts = &parts[0..blobs_index];

    if (parts.len() - blobs_index) < 3 {
        return Err("Malformed resource name: not enough path components after `blobs`".to_owned());
    }

    let size = parts[blobs_index + 2]
        .parse::<usize>()
        .map_err(|_| "Malformed resource name: cannot parse size".to_owned())?;

    let instance_name = if instance_parts.is_empty() {
        ""
    } else {
        let last_instance_name_index =
            instance_parts.iter().map(|x| (*x).len()).sum::<usize>() + instance_parts.len() - 1;
        &resource[0..last_instance_name_index]
    };

    Ok(ParsedReadResourceName {
        instance_name,
        hash: parts[blobs_index + 1],
        size,
    })
}

#[tonic::async_trait]
impl ByteStream for ByteStreamService {
    #[allow(clippy::type_complexity)]
    type ReadStream = SyncWrapper<Pin<Box<dyn Stream<Item = Result<ReadResponse, Status>> + Send>>>;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn read(
        &self,
        request: Request<ReadRequest>,
    ) -> Result<Response<Self::ReadStream>, Status> {
        let request = request.into_inner();

        let parsed_resource_name =
            parse_read_resource_name(&request.resource_name).map_err(Status::invalid_argument)?;

        let digest = Digest::new(parsed_resource_name.hash, parsed_resource_name.size)
            .map_err(Status::invalid_argument)?;

        let instance = Instance {
            name: parsed_resource_name.instance_name.to_owned(),
        };

        let read_offset = match request.read_offset {
            x if x < 0 => return Err(Status::out_of_range("negative read_offset")),
            x if x as usize > digest.size_bytes => {
                return Err(Status::out_of_range(format!(
                    "read_offset exceeds size of resource: {request:?}"
                )))
            }
            0 => None,
            x => Some(x as usize),
        };

        let read_limit = match request.read_limit {
            x if x < 0 => return Err(Status::out_of_range("negative read_limit")),
            0 => None,
            x => Some(x as usize),
        };

        let chunk_stream = match self
            .inner
            .cas
            .read_blob(
                instance,
                digest,
                4 * 1024,
                read_offset,
                read_limit,
                DriverState,
            )
            .await
        {
            Ok(Some(stream)) => {
                let stream = stream.map(move |chunk| {
                    chunk
                        .map(|c| ReadResponse { data: c })
                        .map_err(Status::from)
                });
                Box::pin(stream)
            }
            Ok(None) => return Err(Status::not_found("")),
            Err(err) => return Err(Status::internal(err)),
        };

        Ok(Response::new(SyncWrapper::new(chunk_stream)))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn write(
        &self,
        request: Request<Streaming<WriteRequest>>,
    ) -> Result<Response<WriteResponse>, Status> {
        let mut stream = request.into_inner();

        // Retrieve the first message from the client. This message must have the resource
        // name to write to.
        let msg = match stream.next().await {
            Some(Ok(m)) => m,
            Some(Err(err)) => return Err(err),
            None => return Err(Status::cancelled("client disconnected")),
        };

        let parsed_resource_name =
            parse_write_resource_name(&msg.resource_name).map_err(Status::invalid_argument)?;

        let digest = Digest::new(parsed_resource_name.hash, parsed_resource_name.size)
            .map_err(Status::invalid_argument)?;

        let instance = Instance {
            name: parsed_resource_name.instance_name.to_owned(),
        };

        let write = async move {
            let mut attempt = self
                .inner
                .cas
                .begin_write_blob(instance, digest, DriverState)
                .await?;

            let mut committed_size: i64 = 0;
            let mut next_msg = Some(msg);
            while let Some(msg) = next_msg {
                let chunk_size = msg.data.len() as i64;

                if msg.write_offset != committed_size {
                    return Err(StreamingWriteError::StorageError(StorageError::OutOfRange(
                        "write_offset (vs committed_size)".to_owned(),
                        msg.write_offset as usize,
                    )));
                }

                // Write the current data into the write attempt.
                if !msg.data.is_empty() {
                    attempt.write(msg.data).await?;
                }

                committed_size += chunk_size;

                if msg.finish_write {
                    break;
                }

                next_msg = match stream.next().await {
                    Some(Ok(m)) => Some(m),
                    Some(Err(status)) => {
                        return Err(StreamingWriteError::StorageError(StorageError::Cancelled(
                            format!("client stream error: {status}"),
                        )))
                    }
                    None => {
                        return Err(StreamingWriteError::StorageError(StorageError::Cancelled(
                            "write stream closed without specifying finish_write".to_owned(),
                        )))
                    }
                };
            }

            if committed_size != digest.size_bytes as i64 {
                return Err(StreamingWriteError::StorageError(
                    StorageError::InvalidArgument(
                        "committed size does not match digest size".to_owned(),
                    ),
                ));
            }

            // Commit the write to storage.
            attempt.commit().await?;

            Ok::<i64, StreamingWriteError>(committed_size)
        };

        // If a blob already exists, we should early return with the full size of the digest as
        // the committed_size. See:
        // https://github.com/pantsbuild/pants/blob/89d686fd5fbbec1290cdf32c961af56bc06e1e2e/src/rust/engine/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L250-L254
        let committed_size = write
            .await
            .or_else(|e| match e {
                StreamingWriteError::AlreadyExists => Ok(digest.size_bytes as i64),
                StreamingWriteError::StorageError(e) => Err(e),
            })
            .map_err(Status::from)?;

        Ok(Response::new(WriteResponse { committed_size }))
    }

    /// Query status of a resumable write.
    /// TODO: No need to support this yet because Pants does not support it.
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn query_write_status(
        &self,
        _request: Request<QueryWriteStatusRequest>,
    ) -> Result<Response<QueryWriteStatusResponse>, Status> {
        Err(Status::unimplemented("Not supported"))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        parse_read_resource_name, parse_write_resource_name, ParsedReadResourceName,
        ParsedWriteResourceName,
    };

    #[test]
    fn parse_write_resource_name_correctly() {
        let result = parse_write_resource_name("main/uploads/uuid-12345/blobs/abc123/12").unwrap();
        assert_eq!(
            result,
            ParsedWriteResourceName {
                instance_name: "main",
                _uuid: "uuid-12345",
                hash: "abc123",
                size: 12,
            }
        );

        let result = parse_write_resource_name("uploads/uuid-12345/blobs/abc123/12").unwrap();
        assert_eq!(
            result,
            ParsedWriteResourceName {
                instance_name: "",
                _uuid: "uuid-12345",
                hash: "abc123",
                size: 12,
            }
        );

        let result = parse_write_resource_name("a/b/c/uploads/uuid-12345/blobs/abc123/12").unwrap();
        assert_eq!(
            result,
            ParsedWriteResourceName {
                instance_name: "a/b/c",
                _uuid: "uuid-12345",
                hash: "abc123",
                size: 12,
            }
        );

        // extra components after the size are accepted
        let result =
            parse_write_resource_name("a/b/c/uploads/uuid-12345/blobs/abc123/12/extra/stuff")
                .unwrap();
        assert_eq!(
            result,
            ParsedWriteResourceName {
                instance_name: "a/b/c",
                _uuid: "uuid-12345",
                hash: "abc123",
                size: 12,
            }
        );
    }

    #[test]
    fn parse_write_resource_name_errors_as_expected() {
        let err = parse_write_resource_name("").unwrap_err();
        assert_eq!(err, "Missing resource name");

        let err = parse_write_resource_name("main/uuid-12345/blobs/abc123/12").unwrap_err();
        assert_eq!(err, "Malformed resource name: missing `uploads` component");

        let err = parse_write_resource_name("main/uploads/uuid-12345/abc123/12").unwrap_err();
        assert_eq!(
            err,
            "Malformed resource name: not enough path components after `uploads`"
        );

        let err = parse_write_resource_name("main/uploads/uuid-12345/abc123/12/foo").unwrap_err();
        assert_eq!(err, "Malformed resource name: expected `blobs` component");

        // negative size should be rejected
        let err =
            parse_write_resource_name("main/uploads/uuid-12345/blobs/abc123/-12").unwrap_err();
        assert_eq!(err, "Malformed resource name: cannot parse size");
    }

    #[test]
    fn parse_read_resource_name_correctly() {
        let result = parse_read_resource_name("main/blobs/abc123/12").unwrap();
        assert_eq!(
            result,
            ParsedReadResourceName {
                instance_name: "main",
                hash: "abc123",
                size: 12,
            }
        );

        let result = parse_read_resource_name("blobs/abc123/12").unwrap();
        assert_eq!(
            result,
            ParsedReadResourceName {
                instance_name: "",
                hash: "abc123",
                size: 12,
            }
        );

        let result = parse_read_resource_name("a/b/c/blobs/abc123/12").unwrap();
        assert_eq!(
            result,
            ParsedReadResourceName {
                instance_name: "a/b/c",
                hash: "abc123",
                size: 12,
            }
        );
    }

    #[test]
    fn parse_read_resource_name_errors_as_expected() {
        let err = parse_read_resource_name("").unwrap_err();
        assert_eq!(err, "Missing resource name");

        let err = parse_read_resource_name("main/abc123/12").unwrap_err();
        assert_eq!(err, "Malformed resource name: missing `blobs` component");

        let err = parse_read_resource_name("main/blobs/12").unwrap_err();
        assert_eq!(
            err,
            "Malformed resource name: not enough path components after `blobs`"
        );

        // negative size should be rejected
        let err = parse_read_resource_name("main/blobs/abc123/-12").unwrap_err();
        assert_eq!(err, "Malformed resource name: cannot parse size");
    }
}
