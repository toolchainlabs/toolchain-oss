// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::env;
use std::future::Future;
use std::path::{Path, PathBuf};
use std::pin::Pin;
use std::time::Duration;

use bytes::Bytes;
use futures::task::{noop_waker, Context};
use protos::build::bazel::remote::execution::v2::{
    batch_read_blobs_response, batch_update_blobs_request, batch_update_blobs_response,
    content_addressable_storage_client::ContentAddressableStorageClient, BatchReadBlobsRequest,
    BatchReadBlobsResponse, BatchUpdateBlobsRequest, BatchUpdateBlobsResponse,
    FindMissingBlobsRequest,
};
use regex::bytes::Regex;
use storage::Digest;
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::process::Child;
use tokio::sync::oneshot::Sender;
use tonic::transport::{Channel, Endpoint};

/// Retrieve the output directory for this crate.
// Adapted from https://github.com/rust-lang/cargo/blob/485670b3983b52289a2f353d589c57fae2f60f82/tests/testsuite/support/mod.rs#L507
pub fn target_dir() -> PathBuf {
    env::var_os("CARGO_BIN_PATH")
        .map(PathBuf::from)
        .or_else(|| {
            env::current_exe().ok().map(|mut path| {
                path.pop();
                if path.ends_with("deps") {
                    path.pop();
                }
                path
            })
        })
        .unwrap_or_else(|| panic!("CARGO_BIN_PATH wasn't set. Cannot continue running test"))
}

/// Create a Tonic `Endpoint` from a string containing a schema and IP address/name.
pub fn create_endpoint(addr: &str) -> Result<Endpoint, String> {
    let uri =
        tonic::transport::Uri::try_from(addr).map_err(|err| format!("invalid address: {err}"))?;
    let endpoint = Channel::builder(uri);
    Ok(endpoint)
}

/// Signal the given oneshot channel when a string is found in the given output stream,
/// then drain the output until close to ensure all output is read.
pub async fn scan_for_string_then_drain<R, W>(
    mut reader: R,
    re: Regex,
    sender: Sender<()>,
    mut output_copy: W,
    name: &str,
) where
    R: AsyncRead + Unpin,
    W: AsyncWrite + Unpin,
{
    log::debug!("scan_for_string_then_drain ({}): started", name);

    // Read continually from the pipe until we see Redis boot message.
    let mut buffer = Vec::with_capacity(4096);
    loop {
        let mut read_buf = vec![0; 512];
        match reader.read(&mut read_buf[..]).await {
            Ok(n) if n == 0 => {
                log::error!(
                    "scan_for_string_then_drain ({}): EOF while waiting for expected output",
                    name
                );
                return;
            }
            Ok(n) => {
                log::debug!(
                    "scan_for_string_then_drain ({}): received {} bytes while waiting for string",
                    name,
                    n
                );
                buffer.extend_from_slice(&read_buf[0..n]);
                output_copy.write_all(&read_buf[0..n]).await.unwrap();
                if re.find(&buffer).is_some() {
                    let _ = sender.send(());
                    break;
                }
            }
            Err(err) => {
                log::error!(
                    "scan_for_string_then_drain ({}): failed while waiting for expected output: {}",
                    name,
                    err
                );
                return;
            }
        }
    }
    drop(buffer);

    // Then just drain the output until close.
    loop {
        let mut read_buf = vec![0; 512];
        match reader.read(&mut read_buf[0..]).await {
            Ok(n) if n == 0 => break,
            Ok(n) => {
                output_copy.write_all(&read_buf[0..n]).await.unwrap();
            }
            Err(_) => break,
        }
    }
}

pub async fn drain_to_file<R, W>(mut reader: R, mut writer: W)
where
    R: AsyncRead + Unpin,
    W: AsyncWrite + Unpin,
{
    // Then just drain the output until close.
    loop {
        let mut read_buf = vec![0; 512];
        match reader.read(&mut read_buf[0..]).await {
            Ok(n) if n == 0 => break,
            Ok(n) => {
                writer.write_all(&read_buf[0..n]).await.unwrap();
            }
            Err(_) => break,
        }
    }
}

/// Tokio does not support sending an arbitrary signal (e.g., SIGTERM) to a child process
/// and only uses SIGKILL to terminate a process. This helper is necessary so that SIGTERM
/// can first be sent to the subprocess to give it a chance to exit gracefully..
pub async fn terminate_gracefully(child: &mut Child) {
    // First, send SIGTERM to the subprocess to give it the opportunity to exit gracefully.
    unsafe { libc::kill(child.id().expect("pid") as i32, libc::SIGTERM) };

    // Now wait for the child to exit. If it does not exit gracefully, then send a SIGKILL.
    if let Err(_) = tokio::time::timeout(Duration::from_secs(2), child.wait()).await {
        let _ = child.kill().await;
    }
}

/// Dump the specified file to the console.
pub async fn dump_file(path: impl AsRef<Path>) {
    let contents = tokio::fs::read(path.as_ref()).await.unwrap();
    log::error!(
        "Contents of `{:?}`: {}",
        path.as_ref(),
        String::from_utf8_lossy(&contents)
    )
}

/// A drop guards that will gracefully terminate child processes and also dump an output
/// file if the drop is due to a panic (e.g., a failed test).
pub struct ProcessTerminationGuard(pub Option<Child>, pub Vec<PathBuf>);

impl Drop for ProcessTerminationGuard {
    fn drop(&mut self) {
        let mut child = self.0.take().unwrap();
        let paths = self.1.clone();
        let is_panicking = std::thread::panicking();

        let future = tokio::spawn(async move {
            terminate_gracefully(&mut child).await;
            if is_panicking {
                for path in paths {
                    dump_file(path).await;
                }
            }
        });
        tokio::pin!(future);

        // Spin until the future completes. This is super-hacky but becomes necessary because
        // Tokio no longer exposes a `block_on` method on the `Handle` that would be accessible.
        // It is only exposed on `Runtime` which is no longer accessible here.
        let waker = noop_waker();
        let mut context = Context::from_waker(&waker);
        while Pin::new(&mut future).poll(&mut context).is_pending() {}
    }
}

pub async fn run_integration_test(uri: &str) {
    let content = Bytes::from_static(b"foobar");
    let digest = Digest::of_bytes(&content).unwrap();

    let endpoint = create_endpoint(uri).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());
    let mut cas_client = ContentAddressableStorageClient::new(channel);
    let instance_name = "main".to_owned();

    // Verify that the digest is missing.
    let request = FindMissingBlobsRequest {
        instance_name: instance_name.clone(),
        blob_digests: vec![digest.into()],
    };
    let response = tokio::time::timeout(
        Duration::from_secs(2),
        cas_client.find_missing_blobs(request),
    )
    .await
    .unwrap()
    .unwrap();
    assert_eq!(
        response.into_inner().missing_blob_digests,
        vec![digest.into()]
    );

    // Write the blob to the storage.
    let request = BatchUpdateBlobsRequest {
        instance_name: instance_name.clone(),
        requests: vec![batch_update_blobs_request::Request {
            digest: Some(digest.into()),
            data: content.clone(),
        }],
    };
    let response = tokio::time::timeout(
        Duration::from_secs(2),
        cas_client.batch_update_blobs(request),
    )
    .await
    .unwrap()
    .unwrap()
    .into_inner();
    assert_eq!(
        response,
        BatchUpdateBlobsResponse {
            responses: vec![batch_update_blobs_response::Response {
                digest: Some(digest.into()),
                status: Some(protos::google::rpc::Status {
                    code: protos::google::rpc::Code::Ok as i32,
                    ..protos::google::rpc::Status::default()
                })
            }]
        }
    );

    // Verify that the digest is now present.
    let request = FindMissingBlobsRequest {
        instance_name: instance_name.clone(),
        blob_digests: vec![digest.into()],
    };
    let response = tokio::time::timeout(
        Duration::from_secs(2),
        cas_client.find_missing_blobs(request),
    )
    .await
    .unwrap()
    .unwrap();
    assert!(response.into_inner().missing_blob_digests.is_empty());

    // Read the digest back from the storage and verify its contents.
    let request = BatchReadBlobsRequest {
        instance_name,
        digests: vec![digest.into()],
    };
    let response =
        tokio::time::timeout(Duration::from_secs(2), cas_client.batch_read_blobs(request))
            .await
            .unwrap()
            .unwrap()
            .into_inner();
    assert_eq!(
        response,
        BatchReadBlobsResponse {
            responses: vec![batch_read_blobs_response::Response {
                digest: Some(digest.into()),
                data: content,
                status: Some(protos::google::rpc::Status {
                    code: protos::google::rpc::Code::Ok as i32,
                    ..protos::google::rpc::Status::default()
                }),
            }]
        }
    );
}
