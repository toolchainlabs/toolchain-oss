// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use opentelemetry::sdk::trace::Sampler;
use opentelemetry_otlp::WithExportConfig;
use tracing_subscriber::filter::targets::Targets;
use tracing_subscriber::prelude::*;

use crate::infra::InfraConfig;

/// Configure logging for a binary.
pub fn setup_logging(config: Option<&InfraConfig>, service_name: &'static str) {
    // Note: This cannot use `EnvFilter` because EnvFilter filters globally even if it only
    // used in a tracing stack!
    let filter_layer = {
        let directive = std::env::var("RUST_LOG")
            .ok()
            .unwrap_or_else(|| "info".to_owned());
        directive
            .parse::<Targets>()
            .expect("Failed to parse RUST_LOG")
    };

    let fmt_layer = tracing_subscriber::fmt::layer()
        .json()
        .with_filter(filter_layer);

    let console_layer_opt = std::env::var("TOKIO_CONSOLE_BIND").ok().map(|_| {
        // Enable tokio-console debugging with configuration coming from tokio-console's
        // documented environment variables, i.e. TOKIO_CONSOLE_BIND,
        // TOKIO_CONSOLE_RETENTION, etc.
        console_subscriber::ConsoleLayer::builder()
            .with_default_env()
            .spawn()
    });

    let opentelemetry_layer_opt = config.and_then(|c| c.tracing.as_ref()).map(|tc| {
        if tc.sampling_probability < 0.0 || tc.sampling_probability > 1.0 {
            panic!(
                "sampling_probability must be in range [0.0, 1.0] but was {}",
                tc.sampling_probability
            );
        }

        let otlp_exporter = opentelemetry_otlp::new_exporter()
            .tonic()
            .with_endpoint(&tc.otel_agent);
        let tracer = opentelemetry_otlp::new_pipeline()
            .tracing()
            .with_exporter(otlp_exporter)
            .with_trace_config(
                opentelemetry::sdk::trace::config()
                    .with_sampler(Sampler::ParentBased(Box::new(Sampler::TraceIdRatioBased(
                        tc.sampling_probability,
                    ))))
                    .with_resource(opentelemetry::sdk::Resource::new(vec![
                        opentelemetry::KeyValue::new("service.name", service_name),
                    ])),
            )
            .install_batch(opentelemetry::runtime::Tokio)
            .expect("Failed to set up OpenTelemetry OTLP");

        // Only send opted-into spans to OpenTelemetry (Honeycomb) to reduce noise.
        let filter_layer = tracing_subscriber::filter::FilterFn::new(|metadata| {
            metadata.fields().field("opentelemetry").is_some()
        });

        tracing_opentelemetry::layer()
            .with_tracer(tracer)
            .with_filter(filter_layer)
    });

    tracing_subscriber::registry()
        .with(fmt_layer)
        .with(console_layer_opt)
        .with(opentelemetry_layer_opt)
        .init();
}
