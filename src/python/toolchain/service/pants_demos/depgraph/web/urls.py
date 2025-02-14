# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path

from toolchain.django.site.views.healthz import Healthz
from toolchain.django.site.views.well_known import get_robots_txt_dynamic, get_well_known_urls
from toolchain.pants_demos.depgraph.urls import get_app_urls
from toolchain.util.metrics.prometheus_integration import prometheus_metrics_view

urlpatterns = (
    get_well_known_urls()
    + [
        get_robots_txt_dynamic(),
        path("healthz", Healthz.as_view(), name="healthz"),
        path("metricsz", prometheus_metrics_view, name="prometheus-django-metrics"),
    ]
    + get_app_urls()
)
