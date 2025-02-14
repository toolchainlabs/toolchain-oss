# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path

from toolchain.django.site.views.healthz import Healthz
from toolchain.django.site.views.secretsz import Secretsz
from toolchain.util.metrics.prometheus_integration import prometheus_metrics_view
from toolchain.workflow.worker_views import WorkerStatusz


def get_worker_url_patterns():
    return [
        path("healthz", Healthz.as_view(), name="healthz"),
        path("checksz/secretsz", Secretsz.as_view(), name="secretsz"),
        path("metricsz", prometheus_metrics_view, name="prometheus-django-metrics"),
        path("statusz/", WorkerStatusz.as_view(), name="statusz"),
    ]


urlpatterns = get_worker_url_patterns()
