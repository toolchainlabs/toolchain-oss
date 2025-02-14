// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::{HashMap, HashSet};
use std::future::Future;
use std::sync::Arc;
use std::time::{Duration, Instant};

use arc_swap::ArcSwap;
use futures::{future, Stream};
use ginepro::LoadBalancedChannel;
use grpc_util::auth;
use grpc_util::auth::{AuthScheme, AuthToken, AuthTokenEntry, JWKSet, Permissions};
use grpc_util::backend::{construct_channel, BackendConfig};
use grpc_util::infra::GrpcConfig;
use grpc_util::services::convert_status_code;
use grpc_util::services::GrpcMetrics;
use protos::build::bazel::remote::execution::v2::{
    action_cache_client::ActionCacheClient, action_cache_server::ActionCacheServer,
    capabilities_client::CapabilitiesClient, capabilities_server::CapabilitiesServer,
    content_addressable_storage_client::ContentAddressableStorageClient,
    content_addressable_storage_server::ContentAddressableStorageServer,
    execution_client::ExecutionClient, execution_server::ExecutionServer,
};
use protos::google::bytestream::byte_stream_client::ByteStreamClient;
use protos::google::bytestream::byte_stream_server::ByteStreamServer;
use protos::google::devtools::remoteworkers::v1test2::bots_client::BotsClient;
use protos::google::devtools::remoteworkers::v1test2::bots_server::BotsServer;
use protos::google::longrunning::operations_client::OperationsClient;
use protos::google::longrunning::operations_server::OperationsServer;
use serde::Deserialize;
use tokio::io::{AsyncRead, AsyncWrite};
use tonic::metadata::MetadataMap;
use tonic::transport::server::Connected;
use tonic::transport::Server;
use tonic::{Code, Response, Status};
use tower::ServiceBuilder;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;
use tower_http::metrics::InFlightRequestsLayer;
use tower_http::sensitive_headers::SetSensitiveHeadersLayer;
use tracing::Instrument;

// Modules with particular service proxies.
mod action_cache_service;
mod bots_service;
mod byte_stream_service;
mod capabilities_service;
mod cas_service;
mod execution_service;
mod operations_service;

#[cfg(test)]
mod tests;

pub type InstanceName = String;

#[derive(Clone, Deserialize, Default, Debug)]
pub struct ListenAddressConfig {
    /// IP address on which to listen for connections.
    pub addr: String,
    /// The scheme expected for the authorization bearer token.
    pub auth_scheme: Option<AuthScheme>,
    /// The services that should be supported on this address. A list of fully qualified service
    /// names, e.g. 'build.bazel.remote.execution.v2.ActionCache'.
    pub allowed_service_names: Vec<String>,
}

#[derive(Clone, Deserialize, Default, Debug)]
pub struct BackendTimeoutsConfig {
    /// Timeout for GetActionResult API.
    pub get_action_result: Option<Duration>,
}

/// All of the clients for a single backend.
pub(crate) struct Backend {
    // CAS/AC-specific clients
    pub(crate) cas: ContentAddressableStorageClient<LoadBalancedChannel>,
    pub(crate) action_cache: ActionCacheClient<LoadBalancedChannel>,
    pub(crate) bytestream: ByteStreamClient<LoadBalancedChannel>,
    pub(crate) cas_capabilities: CapabilitiesClient<LoadBalancedChannel>,

    // Execution-specific clients
    pub(crate) execution: Option<ExecutionClient<LoadBalancedChannel>>,
    pub(crate) operations: Option<OperationsClient<LoadBalancedChannel>>,
    pub(crate) bots: Option<BotsClient<LoadBalancedChannel>>,
    pub(crate) _execution_capabilities: Option<CapabilitiesClient<LoadBalancedChannel>>,
}

pub(crate) struct ProxyServerInner {
    /// Per-instance backends.
    instance_backends: HashMap<InstanceName, Backend>,

    /// Backend that will receive all requests which are not routed via per-instance backends.
    catchall_backend: Backend,

    /// The JSON Web Key (JWK) Set used for JWT authentication.
    jwk_set: JWKSet,

    /// A mapping of auth tokens to their auth metadata (for Worker authentication).
    auth_token_mapping: ArcSwap<HashMap<AuthToken, AuthTokenEntry>>,

    /// Timeouts to apply to calls to backends.
    timeouts: BackendTimeoutsConfig,
}

/// A proxy server for Remote Execution API
///
/// `ProxyServer` implements a proxy server for the Remote Execution API and will forward
/// REAPI requests (for both CAS, Action Cache, Execution and other support services) to the
/// appropriate backend service.
#[derive(Clone)]
pub struct ProxyServer {
    inner: Arc<ProxyServerInner>,
}

#[derive(Deserialize, Debug, Default)]
pub struct InstanceConfig {
    /// Address of the remote ContentAddressableStorage service in the form HOST:PORT.
    pub cas: String,

    /// Address of the remote ActionCache service in the form HOST:PORT.
    pub action_cache: String,

    /// Address of the remote Execution service in the form HOST:PORT (optional)
    pub execution: Option<String>,
}

impl ProxyServerInner {
    /// Check that the request is authorized and return an appropriate Status if not.
    #[must_use = "check_authorized result must be examined"]
    pub(crate) fn check_authorized(
        &self,
        auth_scheme: AuthScheme,
        metadata: &MetadataMap,
        requested_instance_name: &str,
        required_permissions: Permissions,
    ) -> Result<(), Status> {
        match auth_scheme {
            AuthScheme::Jwt => {
                let token = auth::get_bearer_token(metadata)?;
                auth::validate_jwt(
                    token,
                    requested_instance_name,
                    required_permissions,
                    &self.jwk_set,
                )
            }
            AuthScheme::AuthToken => {
                let token = auth::get_bearer_token(metadata)?;
                let token_mapping = self.auth_token_mapping.load();
                auth::validate_auth_token(
                    AuthToken::new(token),
                    requested_instance_name,
                    &token_mapping,
                )
            }
            AuthScheme::DevOnlyNoAuth => Ok(()),
        }
    }

    /// Get the backend for the given `instance_name`, or return the catch-all backend if unknown.
    pub(crate) fn backend<'a>(&'a self, instance_name: &'_ str) -> &'a Backend {
        self.instance_backends
            .get(instance_name)
            .unwrap_or(&self.catchall_backend)
    }
}

impl ProxyServer {
    pub async fn new(
        backend_configs: HashMap<String, BackendConfig>,
        per_instance_configs: HashMap<InstanceName, InstanceConfig>,
        catchall_instance_config: InstanceConfig,
        jwk_set: JWKSet,
        auth_token_mapping: HashMap<AuthToken, AuthTokenEntry>,
        timeouts: BackendTimeoutsConfig,
    ) -> Result<ProxyServer, String> {
        // Verify that all InstanceConfigs refers only to known backends.
        Self::validate_instance_config(&backend_configs, &catchall_instance_config)?;
        for instance_config in per_instance_configs.values() {
            Self::validate_instance_config(&backend_configs, instance_config)?;
        }

        // Convert the backends into Tonic channels.
        let (backend_names, backend_configs): (Vec<_>, Vec<_>) =
            backend_configs.into_iter().unzip();
        let backends_fut = backend_configs
            .into_iter()
            .map(construct_channel)
            .collect::<Vec<_>>();

        let backends = backend_names
            .into_iter()
            .zip(future::join_all(backends_fut).await.into_iter())
            .collect::<HashMap<_, _>>();

        let errors = backends
            .iter()
            .filter_map(|(name, endpoint_result)| match endpoint_result {
                Ok(_) => None,
                Err(err) => Some(format!("Failed to create endpoint {name}: {err}")),
            })
            .collect::<Vec<_>>();
        if !errors.is_empty() {
            return Err(errors.as_slice().join("; "));
        }

        let backends = backends
            .into_iter()
            .filter_map(|(name, endpoint_result)| match endpoint_result {
                Ok(endpoint) => Some((name, endpoint)),
                Err(_) => None,
            })
            .collect::<HashMap<_, _>>();

        // Now apply the backends to each configuration.
        let catchall_backend = Self::construct_backend(&backends, catchall_instance_config)?;
        let instance_backends = per_instance_configs
            .into_iter()
            .map(|(instance_name, instance_config)| {
                Ok((
                    instance_name,
                    Self::construct_backend(&backends, instance_config)?,
                ))
            })
            .collect::<Result<HashMap<_, _>, String>>()?;

        Ok(ProxyServer {
            inner: Arc::new(ProxyServerInner {
                instance_backends,
                catchall_backend,
                jwk_set,
                auth_token_mapping: ArcSwap::from(Arc::new(auth_token_mapping)),
                timeouts,
            }),
        })
    }

    fn validate_instance_config(
        backend_configs: &HashMap<String, BackendConfig>,
        instance_config: &InstanceConfig,
    ) -> Result<(), String> {
        let unknown_backend_names = vec![
            Some(instance_config.cas.clone()),
            Some(instance_config.action_cache.clone()),
            instance_config.execution.as_ref().cloned(),
        ]
        .into_iter()
        .flatten()
        .filter(|name| !backend_configs.contains_key(name))
        .collect::<Vec<_>>();
        if !unknown_backend_names.is_empty() {
            return Err(format!(
                "Unknown backend names present in catch-all backend configuration: {}",
                unknown_backend_names.join(", ")
            ));
        }
        Ok(())
    }

    fn construct_backend(
        backends: &HashMap<String, LoadBalancedChannel>,
        instance_config: InstanceConfig,
    ) -> Result<Backend, String> {
        Ok(Backend {
            // CAS/AC-specific services
            cas: ContentAddressableStorageClient::new(
                backends
                    .get(&instance_config.cas)
                    .cloned()
                    .ok_or_else(|| format!("Unknown backend: {}", &instance_config.cas))?,
            ),
            action_cache: ActionCacheClient::new(
                backends
                    .get(&instance_config.action_cache)
                    .cloned()
                    .ok_or_else(|| format!("Unknown backend: {}", &instance_config.action_cache))?,
            ),
            bytestream: ByteStreamClient::new(
                backends
                    .get(&instance_config.cas)
                    .cloned()
                    .ok_or_else(|| format!("Unknown backend: {}", &instance_config.cas))?,
            ),
            cas_capabilities: CapabilitiesClient::new(
                backends
                    .get(&instance_config.cas)
                    .cloned()
                    .ok_or_else(|| format!("Unknown backend: {}", &instance_config.cas))?,
            ),

            // Execution services (optional)
            execution: instance_config
                .execution
                .as_ref()
                .and_then(|name| backends.get(name).cloned().map(ExecutionClient::new)),
            operations: instance_config
                .execution
                .as_ref()
                .and_then(|name| backends.get(name).cloned().map(OperationsClient::new)),
            bots: instance_config
                .execution
                .as_ref()
                .and_then(|name| backends.get(name).cloned().map(BotsClient::new)),
            _execution_capabilities: instance_config
                .execution
                .as_ref()
                .and_then(|name| backends.get(name).cloned().map(CapabilitiesClient::new)),
        })
    }

    pub fn swap_auth_token_mapping(&self, mapping: HashMap<AuthToken, AuthTokenEntry>) {
        self.inner.auth_token_mapping.swap(Arc::new(mapping));
    }

    pub async fn serve_with_incoming_shutdown<I, IO, IE, F>(
        self,
        incoming: I,
        shutdown_signal: F,
        auth_scheme: AuthScheme,
        allowed_service_names: HashSet<String>,
        grpc_config: Option<GrpcConfig>,
        in_flight_requests_counter: InFlightRequestsCounter,
    ) -> Result<(), tonic::transport::Error>
    where
        I: Stream<Item = Result<IO, IE>>,
        IO: AsyncRead + AsyncWrite + Connected + Unpin + Send + 'static,
        IE: Into<Box<dyn std::error::Error + Send + Sync + 'static>>,
        F: Future<Output = ()>,
    {
        let cas_server = if allowed_service_names.contains(cas_service::CasService::SERVICE_NAME) {
            let cas_service = cas_service::CasService::new(self.inner.clone(), auth_scheme);
            Some(GrpcMetrics::new(ContentAddressableStorageServer::new(
                cas_service,
            )))
        } else {
            None
        };

        let bytestream_server = if allowed_service_names
            .contains(byte_stream_service::ByteStreamService::SERVICE_NAME)
        {
            let bytestream_service =
                byte_stream_service::ByteStreamService::new(self.inner.clone(), auth_scheme);
            Some(GrpcMetrics::new(ByteStreamServer::new(bytestream_service)))
        } else {
            None
        };

        let action_cache_server = if allowed_service_names
            .contains(action_cache_service::ActionCacheService::SERVICE_NAME)
        {
            let action_cache_service =
                action_cache_service::ActionCacheService::new(self.inner.clone(), auth_scheme);
            Some(GrpcMetrics::new(ActionCacheServer::new(
                action_cache_service,
            )))
        } else {
            None
        };

        let capabilities_server = if allowed_service_names
            .contains(capabilities_service::CapabilitiesService::SERVICE_NAME)
        {
            let capabilities_service =
                capabilities_service::CapabilitiesService::new(self.inner.clone(), auth_scheme);
            Some(GrpcMetrics::new(CapabilitiesServer::new(
                capabilities_service,
            )))
        } else {
            None
        };

        let execution_server =
            if allowed_service_names.contains(execution_service::ExecutionService::SERVICE_NAME) {
                let execution_service =
                    execution_service::ExecutionService::new(self.inner.clone(), auth_scheme);
                Some(GrpcMetrics::new(ExecutionServer::new(execution_service)))
            } else {
                None
            };

        let operations_server = if allowed_service_names
            .contains(operations_service::OperationsService::SERVICE_NAME)
        {
            let operations_service =
                operations_service::OperationsService::new(self.inner.clone(), auth_scheme);
            Some(GrpcMetrics::new(OperationsServer::new(operations_service)))
        } else {
            None
        };

        let bots_server = if allowed_service_names.contains(bots_service::BotsService::SERVICE_NAME)
        {
            let bots_service = bots_service::BotsService::new(self.inner.clone(), auth_scheme);
            Some(GrpcMetrics::new(BotsServer::new(bots_service)))
        } else {
            None
        };

        let mut server = Server::builder();
        if let Some(c) = grpc_config.as_ref() {
            server = c.apply_to_server(server);
        }

        let in_flight_requests_layer = InFlightRequestsLayer::new(in_flight_requests_counter);
        let auth_header_sensitive_layer =
            SetSensitiveHeadersLayer::new(vec![http::header::AUTHORIZATION]);
        let layer = ServiceBuilder::new()
            .layer(in_flight_requests_layer)
            .layer(auth_header_sensitive_layer)
            .into_inner();

        let router = server
            .layer(layer)
            .add_optional_service(cas_server)
            .add_optional_service(action_cache_server)
            .add_optional_service(bytestream_server)
            .add_optional_service(capabilities_server)
            .add_optional_service(execution_server)
            .add_optional_service(operations_server)
            .add_optional_service(bots_server);

        router
            .serve_with_incoming_shutdown(incoming, shutdown_signal)
            .await
    }
}

/// Drop guard to ensure that the "request finished" metrics is still incremented even if
/// when the client closes its connection.
struct ClientCancelGuard {
    service_name: &'static str,
    service_method: &'static str,
    start_time: Instant,
    completed: bool,
}

impl ClientCancelGuard {
    pub fn new(service_name: &'static str, service_method: &'static str) -> Self {
        ClientCancelGuard {
            service_name,
            service_method,
            start_time: Instant::now(),
            completed: false,
        }
    }

    pub fn complete_for_code(&mut self, code: Code) {
        self.completed = true;

        metrics::histogram!(
            "grpc_client_handling_seconds",
            self.start_time.elapsed(),
            "grpc_service" => self.service_name,
            "grpc_method" => self.service_method,
        );

        metrics::increment_counter!(
            "grpc_client_handled_total",
            "grpc_service" => self.service_name,
            "grpc_method" => self.service_method,
            "grpc_code" => convert_status_code(code as u16),
        );
    }
}

impl Drop for ClientCancelGuard {
    fn drop(&mut self) {
        if !self.completed {
            self.complete_for_code(Code::Cancelled);
        }
    }
}

pub(crate) async fn do_one_client_call<T>(
    f: impl Future<Output = Result<Response<T>, Status>>,
    service_name: &'static str,
    service_method: &'static str,
) -> Result<Response<T>, Status> {
    metrics::increment_counter!(
        "grpc_client_started_total",
        "grpc_service" => service_name.to_owned(),
        "grpc_method" => service_method.to_owned(),
    );

    // Create a drop guard to increment the "request finished" counter if the async task
    // running this function is dropped early.
    let mut cancel_guard = ClientCancelGuard::new(service_name, service_method);

    let result = f
        .instrument(tracing::info_span!(
            "gRPC client call",
            grpc_service = service_name,
            grpc_method = service_method,
            opentelemetry = true
        ))
        .await;

    let code = result.as_ref().err().map(|s| s.code()).unwrap_or(Code::Ok);
    cancel_guard.complete_for_code(code);

    if let Code::Internal
    | Code::Cancelled
    | Code::Unavailable
    | Code::Unknown
    | Code::ResourceExhausted
    | Code::Aborted
    | Code::Unimplemented = code
    {
        log::error!(
            "unexpected backend error for {}.{}: {:?}",
            service_name,
            service_method,
            result.as_ref().err(),
        );
    }

    result
}

fn is_retryable(status: &Status) -> bool {
    matches!(
        status.code(),
        Code::Aborted
            | Code::Cancelled
            | Code::Internal
            | Code::ResourceExhausted
            | Code::Unavailable
            | Code::Unknown
    )
}

#[inline]
pub(crate) async fn client_call<T, C, F, Fut>(
    client: C,
    f: F,
    service_name: &'static str,
    service_method: &'static str,
) -> Result<Response<T>, Status>
where
    C: Clone,
    F: Fn(C) -> Fut,
    Fut: Future<Output = Result<Response<T>, Status>>,
{
    let client2 = client.clone();
    let result_fut = f(client2);
    let mut result = do_one_client_call(result_fut, service_name, service_method).await;
    if let Err(ref status) = result {
        if is_retryable(status) {
            metrics::increment_counter!(
                "toolchain_proxy_retry_backend_requests_total",
                "grpc_service" => service_name.to_owned(),
                "grpc_method" => service_method.to_owned(),
                "grpc_code" => convert_status_code(status.code() as u16),
            );
            let result_fut = f(client);
            result = do_one_client_call(result_fut, service_name, service_method).await;
        }
    }
    result
}
