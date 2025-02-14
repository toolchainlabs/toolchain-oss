# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from opentelemetry import trace  # type: ignore[attr-defined]
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore[attr-defined]
from opentelemetry.sdk.trace import TracerProvider  # type: ignore[attr-defined]
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[attr-defined]


def dummy_trace_client():
    # based on https://docs.honeycomb.io/getting-data-in/python/opentelemetry/s
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().get_tracer(__name__)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
