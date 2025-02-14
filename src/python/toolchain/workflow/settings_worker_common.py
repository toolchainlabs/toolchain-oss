# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import INSTALLED_APPS, K8S_ENV
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if K8S_ENV.is_running_in_kubernetes:
    _pod_ip = K8S_ENV.pod_ip
    if _pod_ip:  # Needed so Prometheus can access the metricsz endpoint.
        ALLOWED_HOSTS.append(_pod_ip)

INSTALLED_APPS.append("toolchain.workflow.apps.WorkflowAppConfig")
CSRF_USE_SESSIONS = False  # Since we don't install session middleware on workflow worker sites.
MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=False)
ROOT_URLCONF = "toolchain.workflow.urls_worker"
