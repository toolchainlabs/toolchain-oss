// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]

use std::net::SocketAddr;
use std::str::FromStr;

use clap::{Arg, Command};
use grpc_util::backend::construct_channel;
use grpc_util::hyper::AddrIncomingWithStream;
use grpc_util::infra::setup_infra_endpoints;
use grpc_util::logging::setup_logging;
use grpc_util::sentry::setup_sentry;
use hyper::server::conn::AddrIncoming;
use protos::build::bazel::remote::execution::v2::content_addressable_storage_client::ContentAddressableStorageClient;
use tokio::io::AsyncReadExt;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;

use execution::api::ExecutionServer;
use execution::serve_with_incoming_shutdown;

pub mod config;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let matches = Command::new("execution_server")
        .arg(
            Arg::new("config")
                .short('c')
                .required(true)
                .value_name("FILE"),
        )
        .get_matches();

    let config = {
        let config_filename = matches.get_one::<String>("config").unwrap();
        let mut file = tokio::fs::File::open(config_filename).await?;
        let mut config_str = String::new();
        file.read_to_string(&mut config_str).await?;
        config::Config::from_str(&config_str).unwrap()
    };

    setup_logging(config.infra.as_ref(), "execution_server");
    log::info!("execution server config: {config:?}");
    let _sentry_guard = setup_sentry(config.infra.as_ref(), "execution_server");

    let cas_client = ContentAddressableStorageClient::new(construct_channel(config.cas).await?);

    let address: SocketAddr = config.listen_address.parse().unwrap();
    let server = ExecutionServer::new(cas_client);

    let incoming = AddrIncoming::bind(&address).expect("failed to bind port");
    log::info!("Serving execution on {}", &address);

    // Setup infra endpoints.
    let in_flight_requests_counter = InFlightRequestsCounter::new();
    let mut shutdown_receiver = {
        let server = server.clone();
        let in_flight_requests_counter = in_flight_requests_counter.clone();
        setup_infra_endpoints(config.infra.unwrap_or_default(), move || {
            server.update_gauges();
            let count = in_flight_requests_counter.get();
            metrics::gauge!("toolchain_grpc_inflight_requests", count as f64, "service" => "execution_server");
        })
        .expect("setup infra endpoints")
    };

    serve_with_incoming_shutdown(
        server,
        AddrIncomingWithStream(incoming),
        async move { while shutdown_receiver.changed().await.is_ok() {} },
        config.grpc,
        in_flight_requests_counter,
    )
    .await?;

    Ok(())
}
