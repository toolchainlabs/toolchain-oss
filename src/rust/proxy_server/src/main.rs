// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]

use std::collections::HashMap;
use std::net::SocketAddr;

use clap::{Arg, Command};
use futures::future;
use hyper::server::conn::AddrIncoming;
use tokio::sync::watch;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;

use grpc_util::hyper::AddrIncomingWithStream;
use grpc_util::infra::{setup_infra_endpoints, GrpcConfig};
use grpc_util::logging::setup_logging;
use grpc_util::sentry::setup_sentry;
use proxy::{ListenAddressConfig, ProxyServer};

mod auth_setup;
mod config;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let matches = Command::new("remoting_proxy")
        .arg(
            Arg::new("config")
                .short('c')
                .required(true)
                .value_name("FILE"),
        )
        .get_matches();

    let config = {
        let filename = matches.get_one::<String>("config").unwrap();
        let config_content = tokio::fs::read_to_string(&filename)
            .await
            .map_err(|err| format!("Failed to read config from {}: {}", &filename, err))?;
        config::Config::from_str(&config_content)?
    };

    setup_logging(config.infra.as_ref(), "proxy_server");
    log::info!("proxy server config: {config:?}");
    let _sentry_guard = setup_sentry(config.infra.as_ref(), "proxy_server");

    let jwk_set = auth_setup::read_jwk_set(&config.jwk_set_path).await?;

    let (maybe_s3_bucket, auth_token_mapping, auth_token_mapping_initial_version) =
        if let Some(ref auth_token_config) = config.auth_token_mapping {
            let s3_bucket = s3::Bucket::new(
                &auth_token_config.s3_bucket,
                auth_token_config.s3_region.parse()?,
                s3::creds::Credentials::from_sts_env("aws-creds")?,
            )?;
            let (auth_token_mapping, auth_token_mapping_initial_version) = futures::try_join!(
                auth_setup::read_auth_token_mapping(&s3_bucket, &auth_token_config.s3_path),
                auth_setup::get_auth_token_mapping_version(&s3_bucket, &auth_token_config.s3_path,),
            )
            .unwrap_or_else(|e: String| {
                auth_setup::log_auth_token_failure(e);
                (HashMap::new(), "".to_owned())
            });
            (
                Some(s3_bucket),
                auth_token_mapping,
                auth_token_mapping_initial_version,
            )
        } else {
            log::warn!("Auth token map disabled because it was not configured");
            (None, HashMap::new(), "".to_owned())
        };

    let backend_timeouts = config
        .backend_timeouts
        .map(|t| t.into_backend_timeouts())
        .unwrap_or_default();

    // Setup infra endpoints.
    let in_flight_requests_counter = InFlightRequestsCounter::new();
    let in_flight_requests_counter_2 = in_flight_requests_counter.clone();
    let shutdown_receiver = setup_infra_endpoints(config.infra.unwrap_or_default(), move || {
        let count = in_flight_requests_counter_2.get();
        metrics::gauge!("toolchain_grpc_inflight_requests", count as f64, "service" => "proxy_server");
    })
    .expect("setup infra endpoints");

    let proxy_server = ProxyServer::new(
        config.backends,
        config.per_instance_backends.unwrap_or_default(),
        config.default_backends,
        jwk_set,
        auth_token_mapping,
        backend_timeouts,
    )
    .await
    .unwrap();

    if let Some(s3_bucket) = maybe_s3_bucket {
        tokio::spawn(auth_setup::refresh_auth_token_mapping(
            s3_bucket,
            config.auth_token_mapping.clone().unwrap(),
            auth_token_mapping_initial_version,
            proxy_server.clone(),
        ));
    }

    let serve_futures = config
        .listen_addresses
        .into_iter()
        .map(|listen_config| {
            serve(
                listen_config,
                proxy_server.clone(),
                in_flight_requests_counter.clone(),
                shutdown_receiver.clone(),
                config.grpc.clone(),
            )
        })
        .collect::<Vec<_>>();
    future::try_join_all(serve_futures).await?;
    Ok(())
}

async fn serve(
    listen_config: ListenAddressConfig,
    proxy_server: ProxyServer,
    in_flight_requests_counter: InFlightRequestsCounter,
    mut shutdown_receiver: watch::Receiver<()>,
    grpc_config: Option<GrpcConfig>,
) -> Result<(), tonic::transport::Error> {
    let address: SocketAddr = listen_config.addr.parse().unwrap();
    let incoming = AddrIncoming::bind(&address).expect("failed to bind port");
    log::info!(
        "Serving proxy on {address} with auth scheme {:?}",
        listen_config.auth_scheme
    );
    proxy_server
        .serve_with_incoming_shutdown(
            AddrIncomingWithStream(incoming),
            async move { while shutdown_receiver.changed().await.is_ok() {} },
            listen_config
                .auth_scheme
                .expect("Must set auth_scheme in config"),
            listen_config.allowed_service_names.into_iter().collect(),
            grpc_config,
            in_flight_requests_counter,
        )
        .await
}
