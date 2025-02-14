# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path

from toolchain.django.site.views.check_infra import CheckSentryz
from toolchain.django.site.views.healthz import Healthz
from toolchain.django.site.views.reloadz import Reloadz
from toolchain.django.site.views.secretsz import Secretsz
from toolchain.util.metrics.prometheus_integration import prometheus_metrics_view


def urlpatterns_base(dependent_resources_check_view=None):
    urls = [
        path("healthz", Healthz.as_view(), name="healthz"),
        path("metricsz", prometheus_metrics_view, name="prometheus-django-metrics"),
        # Everything under checksz is mapped to a different port (in nginx) so it is not accessible via the
        # HTTP port used for API access. see nginx config files (prod/docker/django/nginx/*.conf).
        path("checksz/secretsz", Secretsz.as_view(), name="secretsz"),
        path("checksz/sentryz", CheckSentryz.as_view(), name="sentryz"),
        path("checksz/reloadz", Reloadz.as_view(), name="reloadz"),  # Under
    ]
    if dependent_resources_check_view:
        urls.append(path("checksz/resourcez", dependent_resources_check_view, name="full-health-check"))
    return urls
