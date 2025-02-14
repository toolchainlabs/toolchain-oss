// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::{HashMap, HashSet};
use std::convert::TryInto;
use std::net::{Ipv4Addr, SocketAddr, SocketAddrV4};
use std::str::FromStr;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

use bytes::Bytes;
use futures::{FutureExt, StreamExt};
use grpc_util::auth::{
    generate_jwt, make_jwk_set, make_jwk_set_multiple, AuthScheme, AuthToken, AuthTokenEntry,
    Permissions, TEST_INSTANCE_NAME, TEST_KEY_ID_1, TEST_KEY_ID_2, TEST_SECRET_1, TEST_SECRET_2,
};
use grpc_util::backend::BackendConfig;
use grpc_util::hyper::AddrIncomingWithStream;
use hyper::server::conn::AddrIncoming;
use protos::build::bazel::remote::execution::v2 as remoting_protos;
use protos::build::bazel::remote::execution::v2::{
    action_cache_client::ActionCacheClient, action_cache_server::ActionCache,
    action_cache_server::ActionCacheServer, capabilities_client::CapabilitiesClient,
    capabilities_server::Capabilities, capabilities_server::CapabilitiesServer,
    content_addressable_storage_client::ContentAddressableStorageClient,
    content_addressable_storage_server::ContentAddressableStorage,
    content_addressable_storage_server::ContentAddressableStorageServer,
    execution_client::ExecutionClient, execution_server::Execution,
    execution_server::ExecutionServer, ActionResult, BatchReadBlobsRequest, BatchReadBlobsResponse,
    BatchUpdateBlobsRequest, BatchUpdateBlobsResponse, ExecuteRequest, FindMissingBlobsRequest,
    FindMissingBlobsResponse, GetActionResultRequest, GetCapabilitiesRequest, GetTreeRequest,
    GetTreeResponse, ServerCapabilities, UpdateActionResultRequest, WaitExecutionRequest,
};
use protos::google::bytestream::{
    byte_stream_client::ByteStreamClient, byte_stream_server::ByteStream,
    byte_stream_server::ByteStreamServer, QueryWriteStatusRequest, QueryWriteStatusResponse,
    ReadRequest, ReadResponse, WriteRequest, WriteResponse,
};
use protos::google::longrunning::{
    operations_client::OperationsClient, operations_server::Operations,
    operations_server::OperationsServer, CancelOperationRequest, DeleteOperationRequest,
    GetOperationRequest, ListOperationsRequest, ListOperationsResponse, Operation,
    WaitOperationRequest,
};
use tokio::task::JoinHandle;
use tonic::transport::{Endpoint, Server};
use tonic::{Code, Request, Response, Status, Streaming};
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;

use super::ProxyServer;
use crate::server::{
    action_cache_service, byte_stream_service, capabilities_service, cas_service,
    execution_service, operations_service,
};
use crate::{BackendTimeoutsConfig, InstanceConfig};

fn all_service_names() -> HashSet<String> {
    HashSet::from([
        cas_service::CasService::SERVICE_NAME.to_owned(),
        byte_stream_service::ByteStreamService::SERVICE_NAME.to_owned(),
        action_cache_service::ActionCacheService::SERVICE_NAME.to_owned(),
        capabilities_service::CapabilitiesService::SERVICE_NAME.to_owned(),
        execution_service::ExecutionService::SERVICE_NAME.to_owned(),
        operations_service::OperationsService::SERVICE_NAME.to_owned(),
    ])
}

#[derive(Clone)]
struct MockExecutionServer {
    calls_count: Arc<AtomicUsize>,
}

#[tonic::async_trait]
impl Execution for MockExecutionServer {
    type ExecuteStream = tonic::codec::Streaming<Operation>;

    async fn execute(
        &self,
        _request: Request<ExecuteRequest>,
    ) -> Result<Response<Self::ExecuteStream>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    type WaitExecutionStream = tonic::codec::Streaming<Operation>;

    async fn wait_execution(
        &self,
        _request: Request<WaitExecutionRequest>,
    ) -> Result<Response<Self::WaitExecutionStream>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }
}

#[derive(Clone)]
struct MockCASServer {
    calls_count: Arc<AtomicUsize>,
}

#[tonic::async_trait]
impl ContentAddressableStorage for MockCASServer {
    async fn find_missing_blobs(
        &self,
        _request: Request<FindMissingBlobsRequest>,
    ) -> Result<Response<FindMissingBlobsResponse>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn batch_update_blobs(
        &self,
        _request: Request<BatchUpdateBlobsRequest>,
    ) -> Result<Response<BatchUpdateBlobsResponse>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn batch_read_blobs(
        &self,
        _request: Request<BatchReadBlobsRequest>,
    ) -> Result<Response<BatchReadBlobsResponse>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    type GetTreeStream = tonic::codec::Streaming<GetTreeResponse>;

    async fn get_tree(
        &self,
        _request: Request<GetTreeRequest>,
    ) -> Result<Response<Self::GetTreeStream>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }
}

#[derive(Clone)]
struct MockByteStreamService {
    calls_count: Arc<AtomicUsize>,
    claim_all_exist: bool,
}

#[tonic::async_trait]
impl ByteStream for MockByteStreamService {
    type ReadStream = tonic::codec::Streaming<ReadResponse>;

    async fn read(
        &self,
        _request: Request<ReadRequest>,
    ) -> Result<Response<Self::ReadStream>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn write(
        &self,
        request: Request<Streaming<WriteRequest>>,
    ) -> Result<Response<WriteResponse>, Status> {
        let mut stream = request.into_inner();
        let mut committed_size: i64 = 0;
        while let Some(write_request) = stream.next().await {
            let write_request = write_request?;
            self.calls_count.fetch_add(1, Ordering::SeqCst);
            if self.claim_all_exist {
                // Represents the "blob already exists" case from
                // https://github.com/toolchainlabs/toolchain/blob/9b67e089b865efbc6cbba46ba029f6e355431608/src/rust/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L228-L232
                let (_, total_size_str) = write_request.resource_name.rsplit_once('/').unwrap();
                committed_size = total_size_str.parse().unwrap();
                break;
            }
            let len = write_request.data.len() as i64;
            committed_size += len;
        }
        Ok(Response::new(protos::google::bytestream::WriteResponse {
            committed_size,
        }))
    }

    async fn query_write_status(
        &self,
        _request: Request<QueryWriteStatusRequest>,
    ) -> Result<Response<QueryWriteStatusResponse>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }
}

#[derive(Clone)]
struct MockActionCacheService {
    calls_count: Arc<AtomicUsize>,
    infinite_action_cache: bool,
}

#[tonic::async_trait]
impl ActionCache for MockActionCacheService {
    async fn get_action_result(
        &self,
        _request: Request<GetActionResultRequest>,
    ) -> Result<Response<ActionResult>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        if self.infinite_action_cache {
            futures::future::pending().await
        } else {
            Err(Status::unimplemented("nothing to see here"))
        }
    }

    async fn update_action_result(
        &self,
        _request: Request<UpdateActionResultRequest>,
    ) -> Result<Response<ActionResult>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        if self.infinite_action_cache {
            futures::future::pending().await
        } else {
            Err(Status::unimplemented("nothing to see here"))
        }
    }
}

#[derive(Clone)]
struct MockOperationService {
    calls_count: Arc<AtomicUsize>,
}

#[tonic::async_trait]
impl Operations for MockOperationService {
    async fn list_operations(
        &self,
        _request: Request<ListOperationsRequest>,
    ) -> Result<Response<ListOperationsResponse>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn get_operation(
        &self,
        _request: Request<GetOperationRequest>,
    ) -> Result<Response<Operation>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn delete_operation(
        &self,
        _request: Request<DeleteOperationRequest>,
    ) -> Result<Response<()>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn cancel_operation(
        &self,
        _request: Request<CancelOperationRequest>,
    ) -> Result<Response<()>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }

    async fn wait_operation(
        &self,
        _request: Request<WaitOperationRequest>,
    ) -> Result<Response<Operation>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);
        Err(Status::unimplemented("nothing to see here"))
    }
}

#[derive(Clone)]
struct MockCapabilitiesService {
    calls_count: Arc<AtomicUsize>,
    is_unavailable: Arc<AtomicBool>,
}

#[tonic::async_trait]
impl Capabilities for MockCapabilitiesService {
    async fn get_capabilities(
        &self,
        _request: Request<GetCapabilitiesRequest>,
    ) -> Result<Response<ServerCapabilities>, Status> {
        self.calls_count.fetch_add(1, Ordering::SeqCst);

        // Support `retries_backend_requests_which_are_retryable`.
        if self.is_unavailable.load(Ordering::SeqCst) {
            return Err(Status::unavailable("unavailable"));
        }

        Ok(Response::new(ServerCapabilities::default()))
    }
}

fn add_jwt_to_request<T>(request: &mut Request<T>, key_id: &str, secret: &[u8]) {
    let token = generate_jwt(
        // Execute gives us permission for all services.
        &Permissions::Execute.to_string(),
        TEST_INSTANCE_NAME,
        key_id,
        secret,
    );
    add_auth_token_to_request(request, &token);
}

fn add_auth_token_to_request<T>(request: &mut Request<T>, token: &str) {
    let metadata = request.metadata_mut();
    let header = format!("Bearer {token}");
    metadata.insert(
        tonic::metadata::AsciiMetadataKey::from_str("authorization").unwrap(),
        tonic::metadata::AsciiMetadataValue::try_from(&header).unwrap(),
    );
}

fn make_incoming() -> (AddrIncomingWithStream, SocketAddr) {
    let addr = SocketAddr::V4(SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0));
    let incoming = AddrIncoming::bind(&addr).expect("failed to bind port");
    let local_addr = incoming.local_addr();
    let incoming = AddrIncomingWithStream(incoming);
    (incoming, local_addr)
}

fn setup_mock_server(
    infinite_action_cache: bool,
    byte_stream_claim_all_exist: bool,
) -> (
    Arc<AtomicUsize>,
    SocketAddr,
    JoinHandle<()>,
    AddrIncomingWithStream,
    Arc<AtomicBool>,
) {
    let (mock_server_incoming, mock_server_addr) = make_incoming();
    let (proxy_server_incoming, _) = make_incoming();

    let calls_count = Arc::new(AtomicUsize::new(0));
    let is_unavailable = Arc::new(AtomicBool::new(false));

    let mock_execution_server = {
        let srv = MockExecutionServer {
            calls_count: calls_count.clone(),
        };
        ExecutionServer::new(srv)
    };

    let mock_cas_server = {
        let srv = MockCASServer {
            calls_count: calls_count.clone(),
        };
        ContentAddressableStorageServer::new(srv)
    };

    let mock_bytestream_server = {
        let srv = MockByteStreamService {
            calls_count: calls_count.clone(),
            claim_all_exist: byte_stream_claim_all_exist,
        };
        ByteStreamServer::new(srv)
    };

    let mock_action_cache_server = {
        let srv = MockActionCacheService {
            calls_count: calls_count.clone(),
            infinite_action_cache,
        };
        ActionCacheServer::new(srv)
    };

    let mock_operations_server = {
        let srv = MockOperationService {
            calls_count: calls_count.clone(),
        };
        OperationsServer::new(srv)
    };

    let mock_capabilities_server = {
        let srv = MockCapabilitiesService {
            calls_count: calls_count.clone(),
            is_unavailable: is_unavailable.clone(),
        };
        CapabilitiesServer::new(srv)
    };

    let mock_server_fut = Server::builder()
        .add_service(mock_execution_server)
        .add_service(mock_cas_server)
        .add_service(mock_bytestream_server)
        .add_service(mock_action_cache_server)
        .add_service(mock_operations_server)
        .add_service(mock_capabilities_server)
        .serve_with_incoming(mock_server_incoming);

    let mock_server_handle = tokio::spawn(async move {
        let _ = mock_server_fut.await;
    });

    (
        calls_count,
        mock_server_addr,
        mock_server_handle,
        proxy_server_incoming,
        is_unavailable,
    )
}

#[tokio::test]
async fn test_basic_proxy_functionality() {
    fn add_token<T>(request: &mut Request<T>) {
        add_jwt_to_request(request, TEST_KEY_ID_1, TEST_SECRET_1);
    }

    let (calls_count, mock_server_addr, _mock_server_handle, proxy_server_incoming, _) =
        setup_mock_server(false, false);

    let proxy_server_endpoint: Endpoint = format!("http://{}", proxy_server_incoming.local_addr())
        .try_into()
        .unwrap();

    let mut backend_addresses = HashMap::new();
    backend_addresses.insert(
        "backend".to_owned(),
        BackendConfig {
            address: format!("{mock_server_addr}"),
            connections: 1,
        },
    );

    let instance_config = InstanceConfig {
        execution: Some("backend".to_owned()),
        cas: "backend".to_owned(),
        action_cache: "backend".to_owned(),
    };

    let proxy_server = ProxyServer::new(
        backend_addresses,
        HashMap::new(),
        instance_config,
        make_jwk_set(),
        HashMap::new(),
        BackendTimeoutsConfig::default(),
    )
    .await
    .unwrap();
    let (_shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel::<()>();
    let proxy_server_fut = proxy_server.serve_with_incoming_shutdown(
        proxy_server_incoming,
        shutdown_receiver.map(drop),
        AuthScheme::Jwt,
        all_service_names(),
        None,
        InFlightRequestsCounter::new(),
    );
    let _proxy_server_handle = tokio::spawn(async move {
        let _ = proxy_server_fut.await;
    });

    tokio::time::sleep(Duration::from_secs(2)).await;

    // Create client to send execution call through the proxy.
    let mut execution_client = ExecutionClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    let execute_request = ExecuteRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
        skip_cache_lookup: false,
        action_digest: None,
        execution_policy: None,
        results_cache_policy: None,
    };
    let unauthed_request = Request::new(execute_request.clone());
    let mut authed_request = Request::new(execute_request);
    add_token(&mut authed_request);
    assert_eq!(
        execution_client
            .execute(unauthed_request)
            .await
            .expect_err("")
            .code(),
        Code::Unauthenticated
    );
    let err = execution_client
        .execute(authed_request)
        .await
        .expect_err("");
    assert_eq!(err.code(), Code::Unimplemented);
    assert_eq!(1, calls_count.load(Ordering::SeqCst));

    let mut cas_client = ContentAddressableStorageClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    let find_missing_blobs_request = FindMissingBlobsRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
        blob_digests: vec![remoting_protos::Digest {
            hash: "1234567890".into(),
            size_bytes: 256,
        }],
    };
    let unauthed_request = Request::new(find_missing_blobs_request.clone());
    let mut authed_request = Request::new(find_missing_blobs_request);
    add_token(&mut authed_request);
    assert_eq!(
        cas_client
            .find_missing_blobs(unauthed_request)
            .await
            .expect_err("")
            .code(),
        Code::Unauthenticated
    );
    let err = cas_client
        .find_missing_blobs(authed_request)
        .await
        .expect_err("");
    assert_eq!(err.code(), Code::Unimplemented);
    assert_eq!(2, calls_count.load(Ordering::SeqCst));

    let mut byte_stream_client = ByteStreamClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    let requests_to_stream = vec![
        WriteRequest {
            resource_name: format!("{TEST_INSTANCE_NAME}/uploads/foo/bar"),
            data: Bytes::from_static(&[0; 16]),
            write_offset: 0,
            ..Default::default()
        },
        WriteRequest {
            write_offset: 16,
            data: Bytes::from_static(&[1; 8]),
            ..Default::default()
        },
    ];
    let unauthed_request = Request::new(futures::stream::iter(requests_to_stream.clone()));
    let mut authed_request = Request::new(futures::stream::iter(requests_to_stream));
    add_token(&mut authed_request);
    assert_eq!(
        byte_stream_client
            .write(unauthed_request)
            .await
            .expect_err("")
            .code(),
        Code::Unauthenticated
    );
    let response = byte_stream_client.write(authed_request).await.unwrap();
    assert_eq!(response.into_inner().committed_size, 16 + 8);
    // request count is 2 more than last RPC because it includes received messages
    assert_eq!(4, calls_count.load(Ordering::SeqCst));

    let mut action_cache_client = ActionCacheClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    let get_action_result_request = GetActionResultRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
        ..Default::default()
    };
    let unauthed_request = Request::new(get_action_result_request.clone());
    let mut authed_request = Request::new(get_action_result_request);
    add_token(&mut authed_request);
    assert_eq!(
        action_cache_client
            .get_action_result(unauthed_request)
            .await
            .expect_err("")
            .code(),
        Code::Unauthenticated
    );
    let err = action_cache_client
        .get_action_result(authed_request)
        .await
        .expect_err("");
    assert_eq!(err.code(), Code::Unimplemented);
    assert_eq!(5, calls_count.load(Ordering::SeqCst));

    let mut operations_client = OperationsClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    let get_operation_request = GetOperationRequest {
        name: format!("{TEST_INSTANCE_NAME}/12345"),
    };
    let unauthed_request = Request::new(get_operation_request.clone());
    let mut authed_request = Request::new(get_operation_request);
    add_token(&mut authed_request);
    assert_eq!(
        operations_client
            .get_operation(unauthed_request)
            .await
            .expect_err("")
            .code(),
        Code::Unauthenticated
    );
    let err = operations_client
        .get_operation(authed_request)
        .await
        .expect_err("");
    assert_eq!(err.code(), Code::Unimplemented);
    assert_eq!(6, calls_count.load(Ordering::SeqCst));

    let mut capabilities_client = CapabilitiesClient::connect(proxy_server_endpoint)
        .await
        .unwrap();
    let get_capabilities_request = GetCapabilitiesRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
    };
    let unauthed_request = Request::new(get_capabilities_request.clone());
    let mut authed_request = Request::new(get_capabilities_request);
    add_token(&mut authed_request);
    assert_eq!(
        capabilities_client
            .get_capabilities(unauthed_request)
            .await
            .expect_err("")
            .code(),
        Code::Unauthenticated
    );
    capabilities_client
        .get_capabilities(authed_request)
        .await
        .expect("get_capabilities returns capabilities");
    assert_eq!(7, calls_count.load(Ordering::SeqCst));
}

#[tokio::test]
async fn auth_token_scheme() {
    let (calls_count, mock_server_addr, _mock_server_handle, proxy_server_incoming, _) =
        setup_mock_server(false, false);

    let proxy_server_endpoint: Endpoint = format!("http://{}", proxy_server_incoming.local_addr())
        .try_into()
        .unwrap();

    let mut backend_addresses = HashMap::new();
    backend_addresses.insert(
        "backend".to_owned(),
        BackendConfig {
            address: format!("{mock_server_addr}"),
            connections: 1,
        },
    );

    let instance_config = InstanceConfig {
        execution: Some("backend".to_owned()),
        cas: "backend".to_owned(),
        action_cache: "backend".to_owned(),
    };

    let proxy_server = ProxyServer::new(
        backend_addresses,
        HashMap::new(),
        instance_config,
        make_jwk_set(),
        HashMap::from([
            (
                AuthToken::new("active-token".to_owned()),
                AuthTokenEntry {
                    id: "abc".to_owned(),
                    is_active: true,
                    instance_name: TEST_INSTANCE_NAME.to_owned(),
                    customer_slug: "customer-slug".to_owned(),
                },
            ),
            (
                AuthToken::new("inactive-token".to_owned()),
                AuthTokenEntry {
                    id: "xyz".to_owned(),
                    is_active: false,
                    instance_name: TEST_INSTANCE_NAME.to_owned(),
                    customer_slug: "customer-slug".to_owned(),
                },
            ),
        ]),
        BackendTimeoutsConfig::default(),
    )
    .await
    .unwrap();
    let (_shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel::<()>();
    let proxy_server_fut = proxy_server.serve_with_incoming_shutdown(
        proxy_server_incoming,
        shutdown_receiver.map(drop),
        AuthScheme::AuthToken,
        all_service_names(),
        None,
        InFlightRequestsCounter::new(),
    );
    let _proxy_server_handle = tokio::spawn(async move {
        let _ = proxy_server_fut.await;
    });

    tokio::time::sleep(Duration::from_secs(2)).await;
    let mut capabilities_client = CapabilitiesClient::connect(proxy_server_endpoint)
        .await
        .unwrap();
    let get_capabilities_request = GetCapabilitiesRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
    };

    // Send a request with a valid token.
    let mut request1 = Request::new(get_capabilities_request.clone());
    add_auth_token_to_request(&mut request1, "active-token");
    capabilities_client
        .get_capabilities(request1)
        .await
        .expect("get_capabilities returns capabilities");
    assert_eq!(1, calls_count.load(Ordering::SeqCst));

    // Send a request with an invalid token.
    let mut request2 = Request::new(get_capabilities_request);
    add_auth_token_to_request(&mut request2, "inactive-token");
    let error = capabilities_client
        .get_capabilities(request2)
        .await
        .expect_err("error return");
    assert_eq!(1, calls_count.load(Ordering::SeqCst));
    assert_eq!(Code::Unauthenticated, error.code())
}

/// Tests whether the proxy will accept requests with each configured key in cases where there
/// are multiple keys configured.
#[tokio::test]
async fn handles_auth_with_multiple_key_configured() {
    let (calls_count, mock_server_addr, _mock_server_handle, proxy_server_incoming, _) =
        setup_mock_server(false, false);

    let proxy_server_endpoint: Endpoint = format!("http://{}", proxy_server_incoming.local_addr())
        .try_into()
        .unwrap();

    let mut backend_addresses = HashMap::new();
    backend_addresses.insert(
        "backend".to_owned(),
        BackendConfig {
            address: format!("{mock_server_addr}"),
            connections: 1,
        },
    );

    let instance_config = InstanceConfig {
        execution: Some("backend".to_owned()),
        cas: "backend".to_owned(),
        action_cache: "backend".to_owned(),
    };

    let proxy_server = ProxyServer::new(
        backend_addresses,
        HashMap::new(),
        instance_config,
        make_jwk_set_multiple(),
        HashMap::new(),
        BackendTimeoutsConfig::default(),
    )
    .await
    .unwrap();
    let (_shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel::<()>();
    let proxy_server_fut = proxy_server.serve_with_incoming_shutdown(
        proxy_server_incoming,
        shutdown_receiver.map(drop),
        AuthScheme::Jwt,
        all_service_names(),
        None,
        InFlightRequestsCounter::new(),
    );
    let _proxy_server_handle = tokio::spawn(async move {
        let _ = proxy_server_fut.await;
    });

    tokio::time::sleep(Duration::from_secs(2)).await;
    let mut capabilities_client = CapabilitiesClient::connect(proxy_server_endpoint)
        .await
        .unwrap();
    let get_capabilities_request = GetCapabilitiesRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
    };

    // Send a request with the first key.
    let mut request1 = Request::new(get_capabilities_request.clone());
    add_jwt_to_request(&mut request1, TEST_KEY_ID_1, TEST_SECRET_1);
    capabilities_client
        .get_capabilities(request1)
        .await
        .expect("get_capabilities returns capabilities");
    assert_eq!(1, calls_count.load(Ordering::SeqCst));

    // Send a request with the second key.
    let mut request2 = Request::new(get_capabilities_request.clone());
    add_jwt_to_request(&mut request2, TEST_KEY_ID_2, TEST_SECRET_2);
    capabilities_client
        .get_capabilities(request2)
        .await
        .expect("get_capabilities returns capabilities");
    assert_eq!(2, calls_count.load(Ordering::SeqCst));

    // Send a request using an existing key but without a matching key ID. This should fail.
    let mut request3 = Request::new(get_capabilities_request);
    add_jwt_to_request(&mut request3, "xyzzy", TEST_SECRET_1);
    let error = capabilities_client
        .get_capabilities(request3)
        .await
        .expect_err("error return");
    assert_eq!(2, calls_count.load(Ordering::SeqCst));
    assert_eq!(Code::Unauthenticated, error.code())
}

/// Tests whether the proxy will retry certain requests to the backend.
#[tokio::test]
async fn retries_backend_requests_which_are_retryable() {
    let (calls_count, mock_server_addr, _mock_server_handle, proxy_server_incoming, is_unavailable) =
        setup_mock_server(false, false);

    let proxy_server_endpoint: Endpoint = format!("http://{}", proxy_server_incoming.local_addr())
        .try_into()
        .unwrap();

    let mut backend_addresses = HashMap::new();
    backend_addresses.insert(
        "backend".to_owned(),
        BackendConfig {
            address: format!("{mock_server_addr}"),
            connections: 1,
        },
    );

    let instance_config = InstanceConfig {
        execution: Some("backend".to_owned()),
        cas: "backend".to_owned(),
        action_cache: "backend".to_owned(),
    };

    let proxy_server = ProxyServer::new(
        backend_addresses,
        HashMap::new(),
        instance_config,
        make_jwk_set_multiple(),
        HashMap::new(),
        BackendTimeoutsConfig::default(),
    )
    .await
    .unwrap();
    let (_shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel::<()>();
    let proxy_server_fut = proxy_server.serve_with_incoming_shutdown(
        proxy_server_incoming,
        shutdown_receiver.map(drop),
        AuthScheme::Jwt,
        all_service_names(),
        None,
        InFlightRequestsCounter::new(),
    );
    let _proxy_server_handle = tokio::spawn(async move {
        let _ = proxy_server_fut.await;
    });

    tokio::time::sleep(Duration::from_secs(2)).await;
    let mut capabilities_client = CapabilitiesClient::connect(proxy_server_endpoint)
        .await
        .unwrap();
    let get_capabilities_request = GetCapabilitiesRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
    };

    // Send a request with the first key.
    let mut request = Request::new(get_capabilities_request.clone());
    add_jwt_to_request(&mut request, TEST_KEY_ID_1, TEST_SECRET_1);
    is_unavailable.store(true, Ordering::SeqCst);
    let err = capabilities_client
        .get_capabilities(request)
        .await
        .unwrap_err();
    assert_eq!(err.code(), Code::Unavailable);

    // Expect two calls (not one) to the backend since it will be retried once.
    assert_eq!(2, calls_count.load(Ordering::SeqCst));
}

/// Tests whether the proxy will respect backend timeouts.
#[tokio::test]
async fn times_out_backend_requests() {
    let (_calls_count, mock_server_addr, _mock_server_handle, proxy_server_incoming, _) =
        setup_mock_server(true, false);

    let proxy_server_endpoint: Endpoint = format!("http://{}", proxy_server_incoming.local_addr())
        .try_into()
        .unwrap();

    let mut backend_addresses = HashMap::new();
    backend_addresses.insert(
        "backend".to_owned(),
        BackendConfig {
            address: format!("{mock_server_addr}"),
            connections: 1,
        },
    );

    let instance_config = InstanceConfig {
        execution: Some("backend".to_owned()),
        cas: "backend".to_owned(),
        action_cache: "backend".to_owned(),
    };

    let proxy_server = ProxyServer::new(
        backend_addresses,
        HashMap::new(),
        instance_config,
        make_jwk_set(),
        HashMap::new(),
        BackendTimeoutsConfig {
            get_action_result: Some(Duration::from_micros(100)),
        },
    )
    .await
    .unwrap();
    let (_shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel::<()>();
    let proxy_server_fut = proxy_server.serve_with_incoming_shutdown(
        proxy_server_incoming,
        shutdown_receiver.map(drop),
        AuthScheme::Jwt,
        all_service_names(),
        None,
        InFlightRequestsCounter::new(),
    );
    let _proxy_server_handle = tokio::spawn(async move {
        let _ = proxy_server_fut.await;
    });

    let mut action_cache_client = ActionCacheClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    let get_action_result_request = GetActionResultRequest {
        instance_name: TEST_INSTANCE_NAME.into(),
        ..Default::default()
    };
    let mut request = Request::new(get_action_result_request);
    add_jwt_to_request(&mut request, TEST_KEY_ID_1, TEST_SECRET_1);
    let err = action_cache_client
        .get_action_result(request)
        .await
        .expect_err("");
    assert_eq!(err.code(), Code::Unavailable);
    assert!(err.message().contains("storage backend timeout"));
}

/// Tests that the "early exit for existing blob" case is successful.
#[tokio::test]
async fn early_exit_for_existing_blob() {
    let (
        calls_count,
        mock_server_addr,
        _mock_server_handle,
        proxy_server_incoming,
        _is_unavailable,
    ) = setup_mock_server(false, true);

    let proxy_server_endpoint: Endpoint = format!("http://{}", proxy_server_incoming.local_addr())
        .try_into()
        .unwrap();

    let mut backend_addresses = HashMap::new();
    backend_addresses.insert(
        "backend".to_owned(),
        BackendConfig {
            address: format!("{mock_server_addr}"),
            connections: 1,
        },
    );

    let instance_config = InstanceConfig {
        execution: Some("backend".to_owned()),
        cas: "backend".to_owned(),
        action_cache: "backend".to_owned(),
    };

    let proxy_server = ProxyServer::new(
        backend_addresses,
        HashMap::new(),
        instance_config,
        make_jwk_set_multiple(),
        HashMap::new(),
        BackendTimeoutsConfig::default(),
    )
    .await
    .unwrap();
    let (_shutdown_sender, shutdown_receiver) = tokio::sync::oneshot::channel::<()>();
    let proxy_server_fut = proxy_server.serve_with_incoming_shutdown(
        proxy_server_incoming,
        shutdown_receiver.map(drop),
        AuthScheme::Jwt,
        all_service_names(),
        None,
        InFlightRequestsCounter::new(),
    );
    let _proxy_server_handle = tokio::spawn(async move {
        let _ = proxy_server_fut.await;
    });
    tokio::time::sleep(Duration::from_secs(2)).await;

    let mut byte_stream_client = ByteStreamClient::connect(proxy_server_endpoint.clone())
        .await
        .unwrap();
    // NB: We declare the blob to be of a certain size, even though there are many more WriteRequests
    // in the stream.
    let declared_size = 32;
    let requests_to_stream = (0..1024).map(move |i| WriteRequest {
        resource_name: format!("{TEST_INSTANCE_NAME}/uploads/foo/{declared_size}"),
        write_offset: i * 8,
        data: Bytes::from_static(&[1; 8]),
        ..Default::default()
    });
    let mut request = Request::new(futures::stream::iter(requests_to_stream));
    add_jwt_to_request(&mut request, TEST_KEY_ID_1, TEST_SECRET_1);
    let response = byte_stream_client.write(request).await.unwrap();
    assert_eq!(response.into_inner().committed_size, declared_size);
    // We return early after 1 message is sent, but with the full write size as parsed from the
    // resource name.
    assert_eq!(1, calls_count.load(Ordering::SeqCst));
}
