# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import os
import sys

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.settings.db_config import configure_database_connections  # noqa: F403
from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware
from toolchain.toolshed.config import AuthCookieConfig, DuoAuthConfig
from toolchain.toolshed.constants import (
    ADMIN_APPS,
    ADMIN_DBS,
    AUTH_PIPLINE,
    DEV_ONLY_ADMIN_APPS,
    DEV_ONLY_ADMIN_DBS,
    DJANGO_TEMPLATE_CONFIG,
    TOOLSHED_MIDDLEWARE,
)
from toolchain.toolshed.db_router import RequestContextDBRouter
from toolchain.toolshed.url_names import URLNames

ROOT_URLCONF = "toolchain.toolshed.urls"
TEMPLATES = [DJANGO_TEMPLATE_CONFIG] + get_jinja2_template_config()

INSTALLED_APPS.extend(ADMIN_APPS)
if not TOOLCHAIN_ENV.is_prod and DEV_ONLY_ADMIN_APPS:  # type: ignore[attr-defined]
    INSTALLED_APPS.extend(DEV_ONLY_ADMIN_APPS)


MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.DJANGO, with_csp=False, append_middleware=TOOLSHED_MIDDLEWARE)
CSRF_USE_SESSIONS = True
_TOOLSHED_DOMAIN = ".toolshed.toolchainlabs.com"
ALLOWED_HOSTS = [
    # Useful even on k8s, if curl-ing directly from inside the pod.
    "localhost",
    "127.0.0.1",
    _TOOLSHED_DOMAIN,
]

# Auth settings.
# --------------
AUTHENTICATION_BACKENDS = (
    "toolchain.django.site.auth.toolchain_github.ToolchainGithubOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)
AUTH_USER_MODEL = "site.ToolchainUser"
SOCIAL_AUTH_REDIRECT_IS_HTTPS = TOOLCHAIN_ENV.is_prod  # type: ignore[attr-defined]
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = URLNames.LOGIN
LOGOUT_REDIRECT_URL = LOGIN_URL
SOCIAL_AUTH_LOGIN_ERROR_URL = LOGIN_URL

SESSION_COOKIE_AGE = int(datetime.timedelta(days=14 if TOOLCHAIN_ENV.is_dev else 3).total_seconds())  # type: ignore[attr-defined]

if TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Allow staging.toolshed.toolchainlabs.com & toolshed.toolchainlabs.com to share cookies.
    SESSION_COOKIE_DOMAIN = _TOOLSHED_DOMAIN
    CSRF_TRUSTED_ORIGINS = [f"https://*{_TOOLSHED_DOMAIN}"]
    if TOOLCHAIN_ENV.namespace == "staging":  # type: ignore[attr-defined]
        MAIN_SITE_PREFIX = "https://staging.app.toolchain.com"
    else:
        MAIN_SITE_PREFIX = "https://app.toolchain.com"
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_DOMAIN = "localhost"
    MAIN_SITE_PREFIX = "http://localhost:9500"


_db_access_run = os.environ.get("DEV_ONLY_CONFIGURE_DBS") == "true"
if _db_access_run and not TOOLCHAIN_ENV.is_dev and not TOOLCHAIN_ENV.is_collect_static:  # type: ignore[attr-defined]
    raise ToolchainAssertion(f"DEV_ONLY_CONFIGURE_DBS enabled not in dev env: {TOOLCHAIN_ENV}")

if TOOLCHAIN_ENV.is_prod_or_dev or _db_access_run:  # type: ignore[attr-defined]
    _dbs = ADMIN_DBS if TOOLCHAIN_ENV.is_prod and DEV_ONLY_ADMIN_DBS else ADMIN_DBS + DEV_ONLY_ADMIN_DBS  # type: ignore[attr-defined]
    configure_database_connections(sys.modules[__name__], _dbs)
    DATABASE_ROUTERS[:] = [RequestContextDBRouter(SERVICE_INFO.name)]

    # The django admin code accesses content type on the default DB.
    # Similar to code we have in service/users/ui/settings.py
    # we check for dev/prod in order to avoid doing this when running cert commands (collect_static for example).
    DATABASES["default"] = DATABASES["users"]


SOCIAL_AUTH_GITHUB_SCOPE = ["user:email", "read:user", "read:org"]

if TOOLCHAIN_ENV.is_prod_or_dev and not _db_access_run:  # type: ignore[attr-defined]
    SECRET_KEY = SECRETS_READER.get_secret_or_raise("django-secret-key")
    salt = SECRETS_READER.get_secret_or_raise("toolshed-cookie-salt")
    AUTH_COOKIE_CONFIG = AuthCookieConfig.create(TOOLCHAIN_ENV, salt, SESSION_COOKIE_DOMAIN)
    _github_app_creds = SECRETS_READER.get_json_secret_or_raise("toolshed-admin-github-oauth-app")
    SOCIAL_AUTH_GITHUB_KEY = _github_app_creds["GITHUB_KEY"]
    SOCIAL_AUTH_GITHUB_SECRET = _github_app_creds["GITHUB_SECRET"]
    DUO_CONFIG = DuoAuthConfig.from_secrets(SECRETS_READER)
else:
    SECRET_KEY = "🥷-toolshed💼secret-🤖-toolchain-key-👻"


# See https://python-social-auth.readthedocs.io/en/latest/pipeline.html#authentication-pipeline.
SOCIAL_AUTH_PIPELINE = AUTH_PIPLINE
