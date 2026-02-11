// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::convert::TryInto;
use std::sync::Arc;

use cas_service::CasService;
use digest::Digest;
use futures::{Future, Stream};
use grpc_util::infra::GrpcConfig;
use grpc_util::services::GrpcMetrics;
use itertools::{Either, Itertools};
use protos::build::bazel::remote::execution::v2 as remoting_protos;
use protos::build::bazel::remote::execution::v2::action_cache_server::ActionCacheServer;
use protos::build::bazel::remote::execution::v2::capabilities_server::CapabilitiesServer;
use protos::google::bytestream::byte_stream_server::ByteStreamServer;
use tokio::io::{AsyncRead, AsyncWrite};
use tonic::transport::server::Connected;
use tonic::Status;
use tower::ServiceBuilder;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;
use tower_http::metrics::InFlightRequestsLayer;
use tower_http::sensitive_headers::SetSensitiveHeadersLayer;

use crate::api::action_cache_service::ActionCacheService;
use crate::api::byte_stream_service::ByteStreamService;
use crate::api::capabilities_service::CapabilitiesService;
use crate::driver::BlobStorage;

mod action_cache_service;
mod byte_stream_service;
mod capabilities_service;
mod cas_service;
pub mod sync_wrapper;

#[cfg(test)]
mod tests;

struct InnerServer {
    cas: Arc<dyn BlobStorage + Send + Sync + 'static>,
    action_cache: Arc<dyn BlobStorage + Send + Sync + 'static>,
    max_batch_total_size_bytes: usize,
    check_action_cache_completeness: bool,
    completeness_check_probability: u32,
}

/// The `Server` implements the CAS APIs and adapts them to call into a `BlobStorage` implementation.
pub struct Server {
    inner: Arc<InnerServer>,
}

/// Convert a list of REAPI digests into the internal Digest type.
pub fn convert_digests(digests: Vec<remoting_protos::Digest>) -> Result<Vec<Digest>, Status> {
    let (digests, errors): (Vec<_>, Vec<_>) = digests
        .into_iter()
        .map(|d| d.try_into())
        .partition_map(|r: Result<Digest, String>| match r {
            Ok(d) => Either::Left(d),
            Err(e) => Either::Right(e),
        });

    if !errors.is_empty() {
        return Err(Status::invalid_argument(format!(
            "digest errors: {}",
            errors.join(", ")
        )));
    }

    Ok(digests)
}

impl Server {
    /// Maximum size of blobs to be processed through the batch CAS APIs. This is hard-coded
    /// for now until there is a need to configure it. Default to 4 MB.
    pub const DEFAULT_MAX_BATCH_TOTAL_SIZE_BYTES: usize = 4 * 1024 * 1024;

    pub fn new(
        cas: Box<dyn BlobStorage + Send + Sync + 'static>,
        action_cache: Box<dyn BlobStorage + Send + Sync + 'static>,
        check_action_cache_completeness: bool,
        completeness_check_probability: u32,
    ) -> Self {
        Server {
            inner: Arc::new(InnerServer {
                cas: Arc::from(cas),
                action_cache: Arc::from(action_cache),
                max_batch_total_size_bytes: Self::DEFAULT_MAX_BATCH_TOTAL_SIZE_BYTES,
                check_action_cache_completeness,
                completeness_check_probability,
            }),
        }
    }

    pub async fn serve_with_incoming_shutdown<I, IO, IE, F>(
        self,
        incoming: I,
        shutdown_signal: F,
        grpc_config: Option<GrpcConfig>,
        in_flight_requests_counter: InFlightRequestsCounter,
    ) -> Result<(), tonic::transport::Error>
    where
        I: Stream<Item = Result<IO, IE>>,
        IO: AsyncRead + AsyncWrite + Connected + Unpin + Send + 'static,
        IE: Into<Box<dyn std::error::Error + Send + Sync + 'static>>,
        F: Future<Output = ()>,
    {
        let cas_service = CasService {
            inner: self.inner.clone(),
        };
        let cas_server = remoting_protos::content_addressable_storage_server::ContentAddressableStorageServer::new(cas_service);

        let byte_stream_service = ByteStreamService {
            inner: self.inner.clone(),
        };
        let byte_stream_server = ByteStreamServer::new(byte_stream_service);

        let action_cache_service = ActionCacheService {
            inner: self.inner.clone(),
        };
        let action_cache_server = ActionCacheServer::new(action_cache_service);

        let capabilities_service = CapabilitiesService {
            inner: self.inner.clone(),
        };
        let capabilities_server = CapabilitiesServer::new(capabilities_service);

        let mut server = tonic::transport::Server::builder();
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
            .add_service(GrpcMetrics::new(cas_server))
            .add_service(GrpcMetrics::new(byte_stream_server))
            .add_service(GrpcMetrics::new(action_cache_server))
            .add_service(GrpcMetrics::new(capabilities_server));

        router
            .serve_with_incoming_shutdown(incoming, shutdown_signal)
            .await
    }
}
