# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import os

import prometheus_client
from django.http import HttpResponse
from django_prometheus.middleware import Metrics, PrometheusAfterMiddleware, PrometheusBeforeMiddleware

_EXTENDED_METRICS_NAMES = ["django_http_responses_total_by_status_view_method"]


def wrap_middleware(middlewares: list[str]) -> list[str]:
    wrapped_middleware = ["toolchain.util.metrics.prometheus_integration.ToolchainPrometheusBeforeMiddleware"]
    wrapped_middleware.extend(middlewares)
    wrapped_middleware.append("toolchain.util.metrics.prometheus_integration.ToolchainPrometheusAfterMiddleWare")
    return wrapped_middleware


class CustomMetrics(Metrics):
    def register_metric(self, metric_cls, name, documentation, labelnames=tuple(), **kwargs):
        if name in _EXTENDED_METRICS_NAMES:
            labelnames.extend(["view_type", "customer_id"])
        return super().register_metric(metric_cls, name, documentation, labelnames=labelnames, **kwargs)


class ToolchainPrometheusBeforeMiddleware(PrometheusBeforeMiddleware):
    metrics_cls = CustomMetrics


class ToolchainPrometheusAfterMiddleWare(PrometheusAfterMiddleware):
    metrics_cls = CustomMetrics

    def label_metric(self, metric, request, response=None, **labels):
        if metric._name in _EXTENDED_METRICS_NAMES:
            labels.update(
                view_type=getattr(request, "view_type", None) or "unknown",
                customer_id=getattr(request, "customer_id", None) or "unknown",
            )

        return super().label_metric(metric, request, response, **labels)


def prometheus_metrics_view(request):
    """Exports /metrics as a Django view.

    This is a copy of from django_prometheus.ExportToDjangoView
    """
    if "prometheus_multiproc_dir" in os.environ:
        registry = prometheus_client.CollectorRegistry()
        prometheus_client.multiprocess.MultiProcessCollector(registry)
    else:
        registry = prometheus_client.REGISTRY
    metrics_page = prometheus_client.generate_latest(registry)
    return HttpResponse(metrics_page, content_type=prometheus_client.CONTENT_TYPE_LATEST)


prometheus_metrics_view.view_type = "checks"  # type: ignore[attr-defined]
