# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.config.helpers import get_login_url
from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.spa.config import StaticContentConfig
from toolchain.servicerouter.settings import SERVICE_ROUTER_MIDDLEWARE, TEMPLATES_CFG
from toolchain.users.jwt.keys import JWTSecretData

ROOT_URLCONF = "toolchain.servicerouter.urls"

set_up_databases(__name__, "users")

TEMPLATES = TEMPLATES_CFG
INSTALLED_APPS.extend(
    [
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.servicerouter.apps.ServiceRouterAppConfig",
        # WorkflowAppConfig and UsersAppConfig are temporary until we add UI impersonation checks to users/api.
        "toolchain.workflow.apps.WorkflowAppConfig",
        "toolchain.users.apps.UsersAppConfig",
    ]
)

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    STATIC_CONTENT_CONFIG = StaticContentConfig.from_config(
        k8s_env=K8S_ENV,
        toolchain_env=TOOLCHAIN_ENV,
        aws_region=AWS_REGION,
        config=config,
        secrets_reader=SECRETS_READER,
        namespace=NAMESPACE,
        app_name="frontend",
    )
    STATIC_URL = STATIC_CONTENT_CONFIG.static_url


DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 10  # 10mb, needed for buildsense batch

LOGIN_URL = get_login_url(TOOLCHAIN_ENV, config)

CSP_FRAME_ANCESTORS = ("'none'",)
CSP_DEFAULT_SRC = ("'self'",)
CSP_FONT_SRC = ("fonts.googleapis.com", "fonts.gstatic.com")
CSP_CONNECT_SRC = ("'self'", "sentry.io")
CSP_INCLUDE_NONCE_IN = ("script-src",)

_allowed_script_sources = ["'self'"]
if not IS_RUNNING_ON_K8S:
    # Running locally, with "yarn start" requires adding unsafe-eval
    _allowed_script_sources.append("'unsafe-eval'")
if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    CSP_SCRIPT_SRC = tuple(_allowed_script_sources) + STATIC_CONTENT_CONFIG.domains
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "fonts.googleapis.com") + STATIC_CONTENT_CONFIG.domains
    CSP_IMG_SRC = (
        "'self'",
        "data:",
        # Needed to allow avatars from GitHub.
        # Long term, this presents a risk and we should implement a camo server.
        # https://github.com/toolchainlabs/toolchain/issues/2126
        "*.githubusercontent.com",
        # bitbucket:
        "secure.gravatar.com",
        "bitbucket-assetroot.s3.amazonaws.com",
        "bitbucket.org",
    ) + STATIC_CONTENT_CONFIG.domains


CSP_REPORT_ONLY = False

MIDDLEWARE = SERVICE_ROUTER_MIDDLEWARE

# In dev we want to use the same sentry project.
# For prod, we will use a different sentry project for the frontend SPA.
JS_SENTRY_DSN = config.get("JS_SENTRY_DSN", SENTRY_DSN)

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    SECRET_KEY = SECRETS_READER.get_secret_or_raise("django-secret-key")
JWT_AUTH_KEY_DATA = JWTSecretData.read_settings(TOOLCHAIN_ENV, SECRETS_READER)
AUTH_USER_MODEL = "site.ToolchainUser"
