# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging.config
import os

from toolchain.constants import ToolchainEnv, ToolchainServiceInfo
from toolchain.django.service.toolchain_django_service import ToolchainDjangoService
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import get_allowed_hosts, get_sentry_events_filter
from toolchain.util.config.app_config import AppConfig
from toolchain.util.config.kubernetes_env import KubernetesEnv
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.sentry.sentry_integration import init_sentry_for_django

logger = logging.getLogger(__name__)

# First see which env we're running in.
# -------------------------------------

config = AppConfig.from_env()
K8S_ENV = KubernetesEnv.from_config(config)

IS_RUNNING_ON_K8S = K8S_ENV.is_running_in_kubernetes


if IS_RUNNING_ON_K8S:
    config.apply_config_file()
    NAMESPACE = K8S_ENV.namespace
    TOOLCHAIN_ENV = ToolchainEnv(config["TOOLCHAIN_ENV"]).namespaced(namespace=NAMESPACE, is_local=False)  # type: ignore[attr-defined]
    SERVICE_INFO = ToolchainServiceInfo.from_config(ToolchainDjangoService.get_service_name(), config)

else:
    _tc_env = ToolchainEnv(config.get("TOOLCHAIN_ENV", ToolchainEnv.DEV))  # type: ignore[attr-defined]
    SERVICE_INFO = ToolchainServiceInfo.for_local(ToolchainDjangoService.get_service_name())
    if _tc_env.is_collect_static:  # type: ignore[attr-defined]
        TOOLCHAIN_ENV = _tc_env
        NAMESPACE = "n/a"
    else:
        NAMESPACE = config.get("DEV_NAMESPACE_OVERRIDE") or get_remote_username()
        TOOLCHAIN_ENV = _tc_env.namespaced(namespace=NAMESPACE, is_local=True)  # type: ignore[attr-defined]


# Logging settings.
# We don't allow Django to add its defaults, as they are notoriously difficult to override properly.
if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    LOGGING = get_logging_config(config=config, service_type=SERVICE_INFO.service_type)
    logging.config.dictConfig(LOGGING)


# Timezone settings.
# ------------------

TIME_ZONE = "UTC"
USE_TZ = True


# Common settings.
# -----------------------------

APPEND_SLASH = True
ALLOWED_HOSTS = get_allowed_hosts(IS_RUNNING_ON_K8S, k8s_namespace=NAMESPACE, service_info=SERVICE_INFO)
CSRF_USE_SESSIONS = False  # Since we don't install Django session middleware in most sites.
DEBUG = TOOLCHAIN_ENV.is_dev  # type: ignore[attr-defined]
# The ALB forwards the Host header, and does not set X-Forwarded-Host.
USE_X_FORWARDED_HOST = False


# Static file settings.
# -----------------------------
STATIC_URL = "/static/"
STATICFILES_FINDERS = ("toolchain.django.resources.staticfile_finders.AppDirectoriesResourceFinder",)
STATIC_ROOT = (
    "/staticfiles" if IS_RUNNING_ON_K8S or TOOLCHAIN_ENV.is_collect_static else os.path.expanduser("~/staticfiles")  # type: ignore[attr-defined]
)


SENTRY_DSN = config.get("SERVER_SENTRY_DSN")
if IS_RUNNING_ON_K8S:
    init_sentry_for_django(
        dsn=SENTRY_DSN, environment=NAMESPACE, service_info=SERVICE_INFO, events_filter=get_sentry_events_filter()
    )


INSTALLED_APPS = [
    # Since we configure static files/root settings in this module.
    # Long term, most services (api only, workflow) don't need it so we should refactor out.
    "django.contrib.staticfiles",
]
