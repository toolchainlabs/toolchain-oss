// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::convert::TryFrom;
use std::net::{Ipv4Addr, SocketAddr, SocketAddrV4};

use bytes::BytesMut;
use digest::Digest;
use futures::{FutureExt, StreamExt};
use grpc_util::hyper::AddrIncomingWithStream;
use hyper::server::conn::AddrIncoming;
use prost::Message;
use protos::build::bazel::remote::execution::v2::{
    action_cache_client::ActionCacheClient, batch_read_blobs_response, batch_update_blobs_request,
    batch_update_blobs_response, capabilities_client::CapabilitiesClient,
    command::EnvironmentVariable,
    content_addressable_storage_client::ContentAddressableStorageClient,
    digest_function::Value as DigestFunction_Value, Action, ActionCacheUpdateCapabilities,
    ActionResult, BatchReadBlobsRequest, BatchReadBlobsResponse, BatchUpdateBlobsRequest,
    BatchUpdateBlobsResponse, CacheCapabilities, Command, FindMissingBlobsRequest,
    GetActionResultRequest, GetCapabilitiesRequest, OutputFile, ServerCapabilities,
    UpdateActionResultRequest,
};
use protos::google::bytestream::{
    byte_stream_client::ByteStreamClient, ReadRequest, ReadResponse, WriteRequest, WriteResponse,
};
use tonic::transport::{Channel, Endpoint};
use tonic::Code;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;

use crate::api::Server;
use crate::driver::{BlobStorage, DriverState, Instance, MemoryStorage};
use crate::testutil::TestData;

/// Create a Tonic `Endpoint` from a string containing a schema and IP address/name.
fn create_endpoint(addr: &str) -> Result<Endpoint, String> {
    let uri =
        tonic::transport::Uri::try_from(addr).map_err(|err| format!("invalid address: {err}"))?;
    let endpoint = Channel::builder(uri);
    Ok(endpoint)
}

fn create_storage() -> (MemoryStorage, MemoryStorage, Instance) {
    let instance = Instance {
        name: "main".to_owned(),
    };

    let mut cas = MemoryStorage::new();
    cas.ensure_instance(&instance, DriverState::default());

    let mut action_cache = MemoryStorage::new();
    action_cache.ensure_instance(&instance, DriverState::default());

    (cas, action_cache, instance)
}

struct TestServer {
    pub local_addr: SocketAddr,
    shutdown_sender: Option<tokio::sync::oneshot::Sender<()>>,
}

impl Drop for TestServer {
    fn drop(&mut self) {
        if let Some(s) = self.shutdown_sender.take() {
            let _ = s.send(());
        }
    }
}

fn spawn_server<BS1, BS2>(cas: BS1, action_cache: BS2, check_completeness: bool) -> TestServer
where
    BS1: BlobStorage + Send + Sync + 'static,
    BS2: BlobStorage + Send + Sync + 'static,
{
    let addr = SocketAddr::V4(SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0));
    let incoming = AddrIncoming::bind(&addr).expect("failed to bind port");
    let local_addr = incoming.local_addr();
    let incoming = AddrIncomingWithStream(incoming);

    let (shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel();

    tokio::spawn(async move {
        let server = Server::new(
            Box::new(cas),
            Box::new(action_cache),
            check_completeness,
            1000,
        );

        server
            .serve_with_incoming_shutdown(
                incoming,
                shutdown_receiver.map(drop),
                None,
                InFlightRequestsCounter::new(),
            )
            .await
            .unwrap();
    });

    TestServer {
        local_addr,
        shutdown_sender: Some(shutdown_sender),
    }
}

#[tokio::test]
async fn check_cas_apis() {
    let (storage, action_cache, instance) = create_storage();

    let content = TestData::from_static(b"foobar");

    let server = spawn_server(storage, action_cache, false);

    let endpoint = create_endpoint(&format!("http://{}", server.local_addr)).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());
    let mut cas_client = ContentAddressableStorageClient::new(channel);

    // Verify that the digest is missing.
    let request = FindMissingBlobsRequest {
        instance_name: instance.name.clone(),
        blob_digests: vec![content.digest.into()],
    };
    let response = cas_client.find_missing_blobs(request).await.unwrap();
    assert_eq!(
        response.into_inner().missing_blob_digests,
        vec![content.digest.into()]
    );

    // Write the blob to the storage.
    let write_request = BatchUpdateBlobsRequest {
        instance_name: instance.name.clone(),
        requests: vec![batch_update_blobs_request::Request {
            digest: Some(content.digest.into()),
            data: content.bytes.clone(),
        }],
    };
    let response = cas_client
        .batch_update_blobs(write_request.clone())
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        response,
        BatchUpdateBlobsResponse {
            responses: vec![batch_update_blobs_response::Response {
                digest: Some(content.digest.into()),
                status: Some(protos::google::rpc::Status {
                    code: protos::google::rpc::Code::Ok as i32,
                    ..protos::google::rpc::Status::default()
                })
            }]
        }
    );

    // Verify that the digest is now present.
    let request = FindMissingBlobsRequest {
        instance_name: instance.name.clone(),
        blob_digests: vec![content.digest.into()],
    };
    let response = cas_client.find_missing_blobs(request).await.unwrap();
    assert!(response.into_inner().missing_blob_digests.is_empty());

    // Read the digest back from the storage and verify its contents.
    let request = BatchReadBlobsRequest {
        instance_name: instance.name.clone(),
        digests: vec![content.digest.into()],
    };
    let response = cas_client
        .batch_read_blobs(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        response,
        BatchReadBlobsResponse {
            responses: vec![batch_read_blobs_response::Response {
                digest: Some(content.digest.into()),
                data: content.bytes,
                status: Some(protos::google::rpc::Status {
                    code: protos::google::rpc::Code::Ok as i32,
                    ..protos::google::rpc::Status::default()
                }),
            }]
        }
    );

    // Confirm that re-writing it succeeds.
    let response = cas_client
        .batch_update_blobs(write_request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        response,
        BatchUpdateBlobsResponse {
            responses: vec![batch_update_blobs_response::Response {
                digest: Some(content.digest.into()),
                status: Some(protos::google::rpc::Status {
                    code: protos::google::rpc::Code::Ok as i32,
                    ..protos::google::rpc::Status::default()
                })
            }]
        }
    );
}

#[tokio::test]
async fn check_bytestream_apis() {
    let (storage, action_cache, instance) = create_storage();

    let content = TestData::from_static(b"foobar");

    let server = spawn_server(storage, action_cache, false);

    let endpoint = create_endpoint(&format!("http://{}", server.local_addr)).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());
    let mut cas_client = ContentAddressableStorageClient::new(channel.clone());
    let mut bs_client = ByteStreamClient::new(channel);

    // Verify that the digest is missing.
    let request = FindMissingBlobsRequest {
        instance_name: instance.name.clone(),
        blob_digests: vec![content.digest.into()],
    };
    let response = cas_client.find_missing_blobs(request).await.unwrap();
    assert_eq!(
        response.into_inner().missing_blob_digests,
        vec![content.digest.into()]
    );

    // Write the blob into storage.
    let resource_name = format!(
        "{}/uploads/12345/blobs/{}/{}",
        &instance.name,
        hex::encode(content.digest.hash),
        content.digest.size_bytes
    );
    let write_stream = {
        let resource_name = resource_name.clone();
        let content = content.bytes.clone();
        async_stream::stream! {
        let req1 = WriteRequest {
            resource_name,
            write_offset: 0,
            finish_write: false,
            data: content.slice(0..3),
        };
        yield req1;
        let req2 = WriteRequest {
            resource_name: "".into(),
            write_offset: 3,
            finish_write: true,
            data: content.slice(3..),
        };
        yield req2;
        }
    };
    let response = bs_client.write(write_stream).await.unwrap().into_inner();
    assert_eq!(response, WriteResponse { committed_size: 6 });

    // Verify that the digest is now present.
    let request = FindMissingBlobsRequest {
        instance_name: instance.name.clone(),
        blob_digests: vec![content.digest.into()],
    };
    let response = cas_client.find_missing_blobs(request).await.unwrap();
    assert!(response.into_inner().missing_blob_digests.is_empty());

    // Read the blob back from the storage.
    let request = ReadRequest {
        resource_name: format!(
            "{}/blobs/{}/{}",
            &instance.name,
            hex::encode(content.digest.hash),
            content.digest.size_bytes
        ),
        read_offset: 0,
        read_limit: 0,
    };
    let response = bs_client.read(request).await.unwrap();
    let mut stream = response.into_inner();
    let chunk = stream.next().await.unwrap().unwrap();
    assert_eq!(
        chunk,
        ReadResponse {
            data: content.bytes.clone()
        }
    );
    assert!(stream.next().await.is_none());

    // Confirm that re-writing it succeeds early.
    let write_stream = {
        let resource_name = resource_name.clone();
        let content = content.bytes.clone();
        async_stream::stream! {
        let req1 = WriteRequest {
            resource_name,
            write_offset: 0,
            finish_write: false,
            data: content.slice(0..3),
        };
        yield req1;
        }
    };
    let response = bs_client.write(write_stream).await.unwrap().into_inner();
    assert_eq!(response, WriteResponse { committed_size: 6 });
}

#[tokio::test]
async fn check_action_cache_apis() {
    let (storage, action_cache, instance) = create_storage();

    let server = spawn_server(storage, action_cache, false);

    let endpoint = create_endpoint(&format!("http://{}", server.local_addr)).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());
    let mut client = ActionCacheClient::new(channel);

    let content = TestData::from_static(b"foobar");

    let command = Command {
        arguments: vec![
            "/bin/sh".to_owned(),
            "-c".to_owned(),
            "echo grok".to_owned(),
        ],
        environment_variables: vec![EnvironmentVariable {
            name: "FOO".to_owned(),
            value: "bar".to_owned(),
        }],
        ..Command::default()
    };
    let command_bytes = {
        let mut buffer = BytesMut::with_capacity(command.encoded_len());
        command.encode(&mut buffer).unwrap();
        buffer.freeze()
    };
    let command_digest = Digest::of_bytes(&command_bytes).unwrap();

    let action = Action {
        input_root_digest: Some(Digest::EMPTY.into()),
        command_digest: Some(command_digest.into()),
        ..Action::default()
    };
    let action_bytes = {
        let mut buffer = BytesMut::with_capacity(action.encoded_len());
        action.encode(&mut buffer).unwrap();
        buffer.freeze()
    };
    let action_digest = Digest::of_bytes(&action_bytes).unwrap();

    // Verify that this Action is not cached.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        ..GetActionResultRequest::default()
    };
    let err = client.get_action_result(request).await.unwrap_err();
    assert_eq!(err.code(), Code::NotFound);

    // Update the Action Cache with an ActionResult for this Action.
    let action_result = ActionResult {
        stdout_digest: Some(content.digest.into()),
        exit_code: 1,
        output_files: vec![OutputFile {
            digest: Some(content.digest.into()),
            path: "xyzzy".to_owned(),
            ..OutputFile::default()
        }],
        ..ActionResult::default()
    };
    let request = UpdateActionResultRequest {
        instance_name: instance.name.clone(),
        action_digest: Some(action_digest.into()),
        action_result: Some(action_result.clone()),
        ..UpdateActionResultRequest::default()
    };
    let response = client
        .update_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(response, action_result);

    // Check that this Action is now cached.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        ..GetActionResultRequest::default()
    };
    let response = client
        .get_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(response, action_result);
}

#[tokio::test]
async fn check_handling_of_inlining_data_with_action_cache() {
    let (storage, action_cache, instance) = create_storage();

    let server = spawn_server(storage, action_cache, false);

    let endpoint = create_endpoint(&format!("http://{}", server.local_addr)).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());
    let mut client = ActionCacheClient::new(channel);

    let content1 = TestData::from_static(b"foobar");
    let content2 = TestData::from_static(b"helloworld");

    let command = Command {
        arguments: vec!["/bin/ls".to_owned()],
        ..Command::default()
    };
    let command_bytes = {
        let mut buffer = BytesMut::with_capacity(command.encoded_len());
        command.encode(&mut buffer).unwrap();
        buffer.freeze()
    };
    let command_digest = Digest::of_bytes(&command_bytes).unwrap();

    let action = Action {
        input_root_digest: Some(Digest::EMPTY.into()),
        command_digest: Some(command_digest.into()),
        ..Action::default()
    };
    let action_bytes = {
        let mut buffer = BytesMut::with_capacity(action.encoded_len());
        action.encode(&mut buffer).unwrap();
        buffer.freeze()
    };
    let action_digest = Digest::of_bytes(&action_bytes).unwrap();

    // Update the Action Cache with an ActionResult for this Action.
    let action_result = ActionResult {
        exit_code: 1,
        stdout_raw: content1.bytes.clone(),
        stderr_raw: content2.bytes.clone(),
        ..ActionResult::default()
    };
    let request = UpdateActionResultRequest {
        instance_name: instance.name.clone(),
        action_digest: Some(action_digest.into()),
        action_result: Some(action_result.clone()),
        ..UpdateActionResultRequest::default()
    };
    let maybe_server_modified_action_result = client
        .update_action_result(request)
        .await
        .unwrap()
        .into_inner();

    // The server should have modified the returned ActionResult so that stdout and stderr
    // are no longer inlined.
    let expected_action_result = ActionResult {
        exit_code: 1,
        stdout_digest: Some(content1.digest.into()),
        stderr_digest: Some(content2.digest.into()),
        ..ActionResult::default()
    };
    assert_eq!(maybe_server_modified_action_result, expected_action_result);

    // Check that this ActionResult is also returned by GetActionResult.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        ..GetActionResultRequest::default()
    };
    let action_result = client
        .get_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(action_result, expected_action_result);

    // Now ask for stdout to be returned inline.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        inline_stdout: true,
        ..GetActionResultRequest::default()
    };
    let action_result = client
        .get_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        action_result,
        ActionResult {
            exit_code: 1,
            stdout_digest: Some(content1.digest.into()),
            stdout_raw: content1.bytes.clone(),
            stderr_digest: Some(content2.digest.into()),
            ..ActionResult::default()
        }
    );

    // Now ask for stderr to be returned inline.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        inline_stderr: true,
        ..GetActionResultRequest::default()
    };
    let action_result = client
        .get_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        action_result,
        ActionResult {
            exit_code: 1,
            stdout_digest: Some(content1.digest.into()),
            stderr_digest: Some(content2.digest.into()),
            stderr_raw: content2.bytes.clone(),
            ..ActionResult::default()
        }
    );

    // Now ask for both stdout and stderr to be returned inline.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        inline_stdout: true,
        inline_stderr: true,
        ..GetActionResultRequest::default()
    };
    let action_result = client
        .get_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(
        action_result,
        ActionResult {
            exit_code: 1,
            stdout_digest: Some(content1.digest.into()),
            stdout_raw: content1.bytes.clone(),
            stderr_digest: Some(content2.digest.into()),
            stderr_raw: content2.bytes.clone(),
            ..ActionResult::default()
        }
    );
}

#[tokio::test]
async fn check_capabilities_apis() {
    let (storage, action_cache, instance) = create_storage();

    let server = spawn_server(storage, action_cache, false);

    let endpoint = create_endpoint(&format!("http://{}", server.local_addr)).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());

    let mut client = CapabilitiesClient::new(channel);

    let request = GetCapabilitiesRequest {
        instance_name: instance.name,
    };
    let actual_capabilities = client.get_capabilities(request).await.unwrap().into_inner();
    let expected_capabilities = ServerCapabilities {
        cache_capabilities: Some(CacheCapabilities {
            digest_function: vec![DigestFunction_Value::Sha256 as i32],
            max_batch_total_size_bytes: Server::DEFAULT_MAX_BATCH_TOTAL_SIZE_BYTES as i64,
            action_cache_update_capabilities: Some(ActionCacheUpdateCapabilities {
                update_enabled: true,
            }),
            ..CacheCapabilities::default()
        }),
        ..ServerCapabilities::default()
    };
    assert_eq!(actual_capabilities, expected_capabilities);
}

#[tokio::test]
async fn verify_check_action_completeness_checking() {
    let (storage, action_cache, instance) = create_storage();

    let server = spawn_server(storage, action_cache, true);

    let endpoint = create_endpoint(&format!("http://{}", server.local_addr)).unwrap();
    let channel = Channel::balance_list(vec![endpoint].into_iter());
    let mut action_cache_client = ActionCacheClient::new(channel.clone());
    let mut cas_client = ContentAddressableStorageClient::new(channel);

    let content = TestData::from_static(b"foobar");

    let command = Command {
        arguments: vec![
            "/bin/sh".to_owned(),
            "-c".to_owned(),
            "echo grok".to_owned(),
        ],
        environment_variables: vec![EnvironmentVariable {
            name: "FOO".to_owned(),
            value: "bar".to_owned(),
        }],
        ..Command::default()
    };
    let command_bytes = {
        let mut buffer = BytesMut::with_capacity(command.encoded_len());
        command.encode(&mut buffer).unwrap();
        buffer.freeze()
    };
    let command_digest = Digest::of_bytes(&command_bytes).unwrap();

    let action = Action {
        input_root_digest: Some(Digest::EMPTY.into()),
        command_digest: Some(command_digest.into()),
        ..Action::default()
    };
    let action_bytes = {
        let mut buffer = BytesMut::with_capacity(action.encoded_len());
        action.encode(&mut buffer).unwrap();
        buffer.freeze()
    };
    let action_digest = Digest::of_bytes(&action_bytes).unwrap();

    // Update the Action Cache with an ActionResult for this Action.
    let action_result = ActionResult {
        stdout_digest: Some(content.digest.into()),
        exit_code: 1,
        output_files: vec![OutputFile {
            digest: Some(content.digest.into()),
            path: "xyzzy".to_owned(),
            ..OutputFile::default()
        }],
        ..ActionResult::default()
    };
    let request = UpdateActionResultRequest {
        instance_name: instance.name.clone(),
        action_digest: Some(action_digest.into()),
        action_result: Some(action_result.clone()),
        ..UpdateActionResultRequest::default()
    };
    let response = action_cache_client
        .update_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(response, action_result);

    // Verify that this Action is not cached due to completetness checking not finding the
    // output digest (which has not been stored yet).
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        ..GetActionResultRequest::default()
    };
    let err = action_cache_client
        .get_action_result(request)
        .await
        .unwrap_err();
    assert_eq!(err.code(), Code::NotFound);

    // Now store the digest for output which will allow completeness checking to succeed.
    let request = BatchUpdateBlobsRequest {
        requests: vec![batch_update_blobs_request::Request {
            digest: Some(content.digest.into()),
            data: content.bytes,
        }],
        instance_name: instance.name.clone(),
    };
    cas_client.batch_update_blobs(request).await.unwrap();

    // Check that this Action is now cached.
    let request = GetActionResultRequest {
        action_digest: Some(action_digest.into()),
        instance_name: instance.name.clone(),
        ..GetActionResultRequest::default()
    };
    let response = action_cache_client
        .get_action_result(request)
        .await
        .unwrap()
        .into_inner();
    assert_eq!(response, action_result);
}
