// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]
#![allow(clippy::new_without_default, clippy::len_without_is_empty)]

pub mod api;
pub mod server;

use std::future::Future;

use bytes::BytesMut;
use futures::Stream;
use prost::Message;
use tokio::io::{AsyncRead, AsyncWrite};
use tokio::time::Duration;
use tonic::transport::server::Connected;
use tower::ServiceBuilder;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;
use tower_http::metrics::InFlightRequestsLayer;
use tower_http::sensitive_headers::SetSensitiveHeadersLayer;

use grpc_util::infra::GrpcConfig;
use grpc_util::services::GrpcMetrics;

use crate::api::ExecutionServer;

// TODO: This should be based on gRPC deadlines.
const BOT_POLL_TIMEOUT: Duration = Duration::from_secs(5);

fn any_proto_encode<T: Message>(message: &T) -> prost_types::Any {
    let rust_type_name = std::any::type_name::<T>();
    let proto_type_name = rust_type_name
        .strip_prefix("protos::")
        .unwrap()
        .replace("::", ".");

    let mut buf = BytesMut::with_capacity(message.encoded_len());
    message.encode(&mut buf).unwrap();
    prost_types::Any {
        type_url: format!("type.googleapis.com/{proto_type_name}"),
        value: buf.to_vec(),
    }
}

fn any_proto_decode<T: Message + Default>(value: Option<&prost_types::Any>) -> Result<T, String> {
    let bytes = &value
        .ok_or_else(|| format!("no {} value was set", std::any::type_name::<T>()))?
        .value;
    T::decode(&**bytes).map_err(|e| format!("failed to decode {}: {e}", std::any::type_name::<T>()))
}

pub async fn serve_with_incoming_shutdown<I, IO, IE, F>(
    server: ExecutionServer,
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
    let bots_server =
        protos::google::devtools::remoteworkers::v1test2::bots_server::BotsServer::new(
            server.clone(),
        );
    let capabilities_server =
        protos::build::bazel::remote::execution::v2::capabilities_server::CapabilitiesServer::new(
            server.clone(),
        );
    let execution_server =
        protos::build::bazel::remote::execution::v2::execution_server::ExecutionServer::new(
            server.clone(),
        );
    let operations_server =
        protos::google::longrunning::operations_server::OperationsServer::new(server);

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
        .add_service(GrpcMetrics::new(bots_server))
        .add_service(GrpcMetrics::new(capabilities_server))
        .add_service(GrpcMetrics::new(execution_server))
        .add_service(GrpcMetrics::new(operations_server));

    router
        .serve_with_incoming_shutdown(incoming, shutdown_signal)
        .await
}
