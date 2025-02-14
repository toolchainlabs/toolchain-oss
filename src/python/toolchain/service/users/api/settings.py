# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.config.helpers import get_login_url
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.users.jwt.config import JWTConfig
from toolchain.users.jwt.keys import JWTSecretData

# For access tokens auth flows we render HTML error pages, so we need jinja here.
TEMPLATES = get_jinja2_template_config(add_csp_extension=True)
MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.INTERNAL, with_csp=True)
INSTALLED_APPS.extend(USERS_DB_DJANGO_APPS + ("toolchain.workflow.apps.WorkflowAppConfig",))
ROOT_URLCONF = "toolchain.service.users.api.urls"

# Needed since the /api/v1/token/auth/ page is in this service (the toolchain pants send the user to this endpoint)
# and if the user is not logged in we need to redirect him to login and then back /api/v1/token/auth/
LOGIN_URL = get_login_url(TOOLCHAIN_ENV, config)

REST_FRAMEWORK = get_rest_framework_config()
AUTH_USER_MODEL = "site.ToolchainUser"
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_DEFAULT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'",)
CSP_FONT_SRC = (
    "fonts.googleapis.com",
    "use.fontawesome.com",
    "fonts.gstatic.com",
)
CSP_STYLE_SRC = (
    "'self'",
    "use.fontawesome.com",
    "fonts.googleapis.com",
    "maxcdn.bootstrapcdn.com",
)
CSP_SCRIPT_SRC = ()
CSP_INCLUDE_NONCE_IN = ("script-src",)
CSP_REPORT_ONLY = False
CSP_REPORT_URI = "https://toolchain.report-uri.com/r/d/csp/enforce"


set_up_databases(__name__, "users")

# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"users-api-fake-💼secret-{uuid.uuid4()}-🤖-key-👻"

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    JWT_AUTH_KEY_DATA = JWTSecretData.read_settings(TOOLCHAIN_ENV, SECRETS_READER)
    if TOOLCHAIN_ENV.is_prod:
        TOOLCHAIN_REMOTE_CACHE_ADDRESS = config["REMOTE_CACHE_ADDRESS"]
        ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS = frozenset(config["REMOTE_EXECUTION_CUSTOMER_SLUGS"])
    else:
        TOOLCHAIN_REMOTE_CACHE_ADDRESS = config.get("REMOTE_CACHE_ADDRESS", "localhost:8980")
        # In dev (specifically localdev) we want to allow REMOTE_EXECUTION_CUSTOMER_SLUGS to be empty
        ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS = frozenset(config.get("REMOTE_EXECUTION_CUSTOMER_SLUGS", []))
    logger.info(f"remote exec customer slugs: {', '.join(ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS)}")
    JWT_CONFIG = JWTConfig.for_prod() if TOOLCHAIN_ENV.is_prod else JWTConfig.for_dev()  # type: ignore[attr-defined]
