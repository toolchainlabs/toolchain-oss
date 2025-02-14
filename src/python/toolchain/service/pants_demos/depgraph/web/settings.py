# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import boto3

from toolchain.django.site.settings.base import *  # noqa: F401, F403
from toolchain.django.site.settings.db_config import DjangoDBDict, set_up_databases
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware
from toolchain.django.spa.config import StaticContentConfig
from toolchain.pants_demos.depgraph.constants import TEMPLATES_CONFIG
from toolchain.util.secret.secrets_accessor_factories import get_secrets_reader

# SECURITY WARNING: keep the secret key used in production secret!
# TODO: Use an actual prod secret from SECRETS_READER
SECRET_KEY = "django-insecure-d)@o5aab_r-@!hu4u@%dj@5o--r7ych%mqiff(h7f=e4yvy1y)"

_use_remote_dbs = config.is_set("USE_REMOTE_DEV_DBS")
SECRETS_READER = get_secrets_reader(
    toolchain_env=TOOLCHAIN_ENV, is_k8s=IS_RUNNING_ON_K8S, use_remote_dbs=_use_remote_dbs, k8s_namespace=NAMESPACE
)
INSTALLED_APPS.extend(
    [
        "django.contrib.contenttypes",
        "django.contrib.sitemaps",
        "django_extensions",
        "toolchain.django.postgres_setrole.setrole.DjangoPostgreSQLSetRoleApp",
        "django_prometheus",
        "toolchain.workflow.apps.WorkflowAppConfig",
        "toolchain.pants_demos.depgraph.apps.PantsDepgraphDemoApp",
    ]
)

MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=True)
ROOT_URLCONF = "toolchain.service.pants_demos.depgraph.web.urls"
TEMPLATES = TEMPLATES_CONFIG


AWS_REGION = boto3.client("s3").meta.region_name
# Set up databases.
# -----------------

# Django chokes if the 'default' isn't present at all, but it can be set to an empty dict, which
# will be treated as a dummy db.  A call to set_up_database() can override this with real db settings.
DATABASES: DjangoDBDict = {"default": {}}
DATABASE_ROUTERS = []  # type: ignore


set_up_databases(__name__, "pants_demos")


# In dev we want to use the same sentry project.
# For prod, we will use a different sentry project for the frontend SPA.
JS_SENTRY_DSN = config.get("JS_SENTRY_DSN", SENTRY_DSN)

if TOOLCHAIN_ENV.is_prod:
    # https://infosec.mozilla.org/guidelines/web_security#http-strict-transport-security
    SECURE_HSTS_SECONDS = int(datetime.timedelta(days=180).total_seconds())
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


CSP_FRAME_ANCESTORS = ("'none'",)
CSP_DEFAULT_SRC = ("'self'",)
CSP_FONT_SRC = ("'self'", "fonts.gstatic.com")  # not sure we need self...
CSP_CONNECT_SRC = ("'self'", "sentry.io", "www.google-analytics.com")
CSP_INCLUDE_NONCE_IN = ("script-src",)

if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    ALLOWED_HOSTS.append("tcdemositepreview.ngrok.io")
    # This header only works properly over https and we don't use https in dev.
    # https://docs.djangoproject.com/en/4.0/ref/middleware/#cross-origin-opener-policy
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None

REPOS_DISABLE_INDEXING = frozenset(config.get("REPOS_DISABLE_INDEXING", []))

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    STATIC_CONTENT_CONFIG = StaticContentConfig.from_config(
        k8s_env=K8S_ENV,
        toolchain_env=TOOLCHAIN_ENV,
        aws_region=AWS_REGION,
        config=config,
        secrets_reader=SECRETS_READER,
        namespace=NAMESPACE,
        app_name="pants-demo-site",
    )
    STATIC_URL = STATIC_CONTENT_CONFIG.static_url
    _allowed_script_sources = [
        "'self'",
        "cdnjs.cloudflare.com",
        "www.googletagmanager.com",
        "toolchainlabs.us19.list-manage.com",
    ]
    if not IS_RUNNING_ON_K8S:
        # Running locally, with "yarn start" requires adding unsafe-eval
        _allowed_script_sources.append("'unsafe-eval'")

    CSP_SCRIPT_SRC = tuple(_allowed_script_sources) + STATIC_CONTENT_CONFIG.domains
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "fonts.googleapis.com") + STATIC_CONTENT_CONFIG.domains
    CSP_IMG_SRC = (
        "'self'",
        "data:",
        "*.githubusercontent.com",
    ) + STATIC_CONTENT_CONFIG.domains
