// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::net::SocketAddr;

use futures::FutureExt;
use metrics_exporter_prometheus::{PrometheusBuilder, PrometheusHandle};
use serde::Deserialize;
use tokio::runtime::Builder;
use tokio::signal::unix::{signal, SignalKind};
use tokio::sync::watch;
use warp::Filter;

/// Default Prometheus histogram buckets.
/// These have been chosen to hopefully be better for latencies internal to the AWS cloud.
/// Originally, these were set to the default used by the [Prometheus Go client], but those
/// defaults are more useful for Web API calls over the Internet and less so for internal data
/// center requests.
/// [Prometheus Go client]: https://github.com/prometheus/client_golang/blob/9ef86855d4e52661184748b7a6fd9ed39985b479/prometheus/histogram.go#L63
const DEFAULT_PROMETHEUS_BUCKETS: &[f64] = &[
    0.0005, // 0.5 ms
    0.001,  // 1 ms
    0.002,  // 2 ms
    0.003,  // 3 ms
    0.004,  // 4 ms
    0.005,  // 5 ms
    0.010,  // 10 ms
    0.020,  // 20 ms
    0.030,  // 30 ms
    0.040,  // 40 ms
    0.050,  // 50 ms
    0.100,  // 100 ms
    0.250,  // 250 ms
    0.5,    // 500 ms
    1.0,    // 1 sec
    2.5,    // 2.5 secs
    5.0,    // 5 secs
    10.0,   // 10 secs
    30.0,   // 30 secs
];

/// Admin endpoints configuration.
#[derive(Clone, Debug, Deserialize)]
pub struct InfraConfig {
    /// Bind address for the metricsz endpoint.
    #[serde(default = "default_metricsz_bind_addr")]
    pub metricsz_bind_addr: String,

    /// Bind address for the other infra endpoints.
    #[serde(default = "default_bind_addr")]
    pub bind_addr: String,

    /// Sentry DSN
    pub sentry_dsn: Option<String>,

    /// Tracing configuration
    pub tracing: Option<TracingConfig>,
}

impl Default for InfraConfig {
    fn default() -> Self {
        InfraConfig {
            metricsz_bind_addr: default_metricsz_bind_addr(),
            bind_addr: default_bind_addr(),
            sentry_dsn: None,
            tracing: None,
        }
    }
}

/// Tracing configuration
#[derive(Clone, Debug, Deserialize)]
pub struct TracingConfig {
    /// OpenTelemetry agent endpoint, e.g. `http://otel_collector:4317`
    pub otel_agent: String,

    /// Sampling probability used by the OpenTelemetry subscriber.
    ///
    /// Expects a number from 0.0 to 1.0, where higher numbers mean more events will be sent.
    pub sampling_probability: f64,
}

fn default_metricsz_bind_addr() -> String {
    "0.0.0.0:8010".to_owned()
}

fn default_bind_addr() -> String {
    "0.0.0.0:8000".to_owned()
}

/// Configuration of gRPC-specific properties.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
pub struct GrpcConfig {
    /// Number of in-flight requests allowed inbound per connection.
    pub concurrency_limit_per_connection: Option<usize>,

    /// Max number of HTTP/2 concurrent streams.
    pub max_concurrent_streams: Option<u32>,
}

impl GrpcConfig {
    pub fn apply_to_server(
        &self,
        mut server: tonic::transport::Server,
    ) -> tonic::transport::Server {
        if let Some(limit) = self.concurrency_limit_per_connection {
            server = server.concurrency_limit_per_connection(limit);
        }

        if let Some(limit) = self.max_concurrent_streams {
            server = server.max_concurrent_streams(limit)
        }

        server
    }
}

/// Setup metrics collection and scraping endpoint.
fn setup_metrics_handler() -> Result<PrometheusHandle, String> {
    // Build the Prometheus metrics recorder and exporter.
    let recorder = PrometheusBuilder::new()
        .set_buckets(DEFAULT_PROMETHEUS_BUCKETS)
        .map_err(|err| format!("Failed to install set histogram buckets: {err}"))?
        .build_recorder();
    let handle = recorder.handle();
    metrics::set_boxed_recorder(Box::new(recorder))
        .map_err(|err| format!("Failed to install Prometheus metrics recorder: {err}"))?;
    Ok(handle)
}

/// Setup infra endpoints for use by devops systems.
///
/// Returns a `sync::watch` receiver that should be used by all servers as a signal for when they
/// should be shut down by looking for RecvError when calling `.changed()`.
pub fn setup_infra_endpoints(
    config: InfraConfig,
    run_before_metrics_collection: impl Fn() + Clone + Send + Sync + 'static,
) -> Result<watch::Receiver<()>, String> {
    // Setup metrics collection.
    let metrics_handle = setup_metrics_handler()?;

    let metricsz_bind_addr: SocketAddr = config
        .metricsz_bind_addr
        .parse()
        .map_err(|err| format!("Failed to parse metricsz bind address: {err}"))?;

    let bind_addr: SocketAddr = config
        .bind_addr
        .parse()
        .map_err(|err| format!("Failed to parse infra bind address: {err}"))?;

    // Setup shutdown signal handler.
    let (shutdown_sender, shutdown_receiver) = watch::channel(());

    // Spawn a thread for all admin tasks to isolate them from the main event loop.
    std::thread::spawn(move || {
        let runtime = Builder::new_current_thread()
            .enable_all()
            .thread_name("admin")
            .build()
            .expect("initialize admin event loop");

        runtime.block_on(async move {
            let mut sigint_stream = signal(SignalKind::interrupt())
                .map_err(|err| format!("Failed to create SIGINT handler: {err}"))
                .expect("attach SIGINT handler");
            let mut sigterm_stream = signal(SignalKind::terminate())
                .map_err(|err| format!("Failed to create SIGTERM handler: {err}"))
                .expect("attach SIGTERM handler");
            tokio::spawn(async move {
                futures::future::select(
                    sigint_stream.recv().boxed(),
                    sigterm_stream.recv().boxed(),
                )
                .await;
                log::info!("Received shutdown signal. Starting graceful shutdown ...");
                // This will cause all receivers to get RecvError when calling `.changed()`.
                drop(shutdown_sender);
            });

            // Setup health endpoint.
            let healthz = warp::path("healthz").and(warp::get()).map(|| "OK");

            // Build Warp handler to render the metrics.
            let metrics = warp::path!("metricsz").and(warp::get()).map(move || {
                run_before_metrics_collection();
                metrics_handle.render()
            });
            let metrics_fut = warp::serve(metrics).bind(metricsz_bind_addr);

            // Setup the sentry check endpoint.
            let sentryz = warp::path("checksz")
                .and(warp::path("sentryz"))
                .and(warp::post())
                .map(|| {
                    use sentry::protocol::{Event, Level};
                    use sentry::types::Uuid;

                    let event = Event {
                        event_id: Uuid::new_v4(),
                        level: Level::Error,
                        message: Some("checksz/sentryz triggered!".into()),
                        ..Event::default()
                    };

                    sentry::capture_event(event);

                    "OK"
                });

            // Spawn the infra endpoints server.
            let server_fut = warp::serve(healthz.or(sentryz)).bind(bind_addr);

            // Join on both admin servers.
            futures::future::join(server_fut, metrics_fut).await
        });
    });

    Ok(shutdown_receiver)
}

#[cfg(test)]
mod tests {
    use reqwest::StatusCode;
    use tokio::time::{sleep, Duration};

    use super::{setup_infra_endpoints, InfraConfig};

    #[tokio::test]
    async fn infra_endpoints_respond() {
        let config = InfraConfig::default();
        setup_infra_endpoints(config, || {}).unwrap();

        // `warp` does not give us a way to wait until it has finished binding.
        sleep(Duration::from_millis(500)).await;

        // test /healthz
        let response = reqwest::get("http://127.0.0.1:8000/healthz").await.unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let body = response.text().await.unwrap();
        assert_eq!(body, "OK");

        // test /metricsz
        metrics::increment_counter!("test_counter");
        let response = reqwest::get("http://127.0.0.1:8010/metricsz")
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert!(response.text().await.unwrap().contains("test_counter"));
    }
}
