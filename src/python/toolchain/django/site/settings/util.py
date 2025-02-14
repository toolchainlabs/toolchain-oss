# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from enum import Enum, unique

from botocore.auth import NoCredentialsError
from botocore.credentials import CredentialRetrievalError
from colors import cyan, green

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainServiceInfo
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.util.metrics.prometheus_integration import wrap_middleware
from toolchain.util.net.net_util import can_connect
from toolchain.util.sentry.sentry_integration import SentryEventsFilter

logger = logging.getLogger(__name__)


@unique
class MiddlewareAuthMode(Enum):
    NONE = "none"
    DJANGO = "django"
    INTERNAL = "internal"


_AUTH_MIDDLEWARE_MAP = {
    MiddlewareAuthMode.NONE: (),
    MiddlewareAuthMode.DJANGO: (
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
    ),
    MiddlewareAuthMode.INTERNAL: ("toolchain.django.auth.middleware.InternalServicesMiddleware",),
}


def get_rest_framework_config(with_permissions=True, **additional):
    logger.info(f"Configure REST framework: with_permissions={with_permissions}")
    config = {
        "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
        "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
        "PAGE_SIZE": 20,
        "DEFAULT_PAGINATION_CLASS": "toolchain.django.site.utils.pagination_api.ToolchainCursorPagination",
    }
    if with_permissions:
        config["DEFAULT_PERMISSION_CLASSES"] = ("rest_framework.permissions.IsAuthenticated",)
    if additional:
        config.update(additional)
    return config


def get_middleware(
    auth_mode: MiddlewareAuthMode | None,
    with_csp=False,
    prepend_middleware: tuple[str, ...] | None = None,
    append_middleware: tuple[str, ...] | None = None,
    auth_middleware: tuple[str, ...] | None = None,
):
    if auth_mode and auth_middleware:
        raise ToolchainAssertion("setting both auth_mode and auth_middleware is not allowed")
    if auth_mode:
        auth_middleware = _AUTH_MIDDLEWARE_MAP[auth_mode]
    logger.info(f"Configure middleware: {auth_middleware=} CSP={with_csp}")
    middleware = [
        "toolchain.django.site.middleware.request_middleware.ToolchainRequestMiddleware",
        "toolchain.django.site.middleware.error_middleware.TransientErrorsMiddleware",
    ]
    if prepend_middleware:
        middleware.extend(prepend_middleware)
    if with_csp:
        middleware.append("csp.middleware.CSPMiddleware")
    middleware.extend(
        [
            "django.middleware.security.SecurityMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.common.CommonMiddleware",
        ]
    )
    if auth_middleware:
        middleware.extend(auth_middleware)
    if append_middleware:
        middleware.extend(append_middleware)
    return wrap_middleware(middleware)


def get_sentry_events_filter() -> SentryEventsFilter:
    return SentryEventsFilter(CredentialRetrievalError, NoCredentialsError)


def maybe_prompt_k8s_port_fwd(
    *,
    local_port: int,
    remote_port: int,
    namespace: str,
    prompt: str,
    service: str,
    cluster: KubernetesCluster = KubernetesCluster.DEV,
) -> None:
    if can_connect("localhost", local_port):
        return
    print(cyan(prompt))
    print(
        green(
            f"   kubectl --context {cluster.value} port-forward --namespace {namespace} service/{service} {local_port}:{remote_port}"
        )
    )
    input(cyan("Once you have done so, press enter to continue..."))


def get_allowed_hosts(is_running_in_k8s: bool, k8s_namespace: str, service_info: ToolchainServiceInfo) -> list[str]:
    allowed_hosts = [
        # Useful even on k8s, if curl-ing directly from inside the pod.
        "localhost",
        "127.0.0.1",
        # nginx hardcodes the Host header to toolchain.com for healthchecks (/healhz).
        ".toolchain.com",
    ]
    if is_running_in_k8s and service_info.name:
        _k8s_svc_name = service_info.name.replace("/", "-")
        _service_domain = f"{_k8s_svc_name}.{k8s_namespace}.svc.cluster.local"
        logger.info(f"Starting service: {service_info.name} ({_service_domain})")
        allowed_hosts.append(_service_domain)
    return allowed_hosts


def get_memory_cache(location: str) -> dict:
    # https://docs.djangoproject.com/en/3.2/topics/cache/#cache-arguments
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": location,
            "TIMEOUT": 600,  # 10min
            "OPTIONS": {
                "MAX_ENTRIES": 100,
                "CULL_FREQUENCY": 2,
            },
        }
    }
