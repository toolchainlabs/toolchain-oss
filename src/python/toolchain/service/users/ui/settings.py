# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.config.helpers import get_login_url
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import get_rest_framework_config
from toolchain.users.constants import CURRENT_TOS_VERSION, USERS_DB_DJANGO_APPS
from toolchain.users.jwt.keys import JWTSecretData
from toolchain.users.ui.constants import USERS_SOCIAL_AUTH_PIPELINE, USERS_UI_MIDDLEWARE
from toolchain.users.ui.url_names import URLNames

ROOT_URLCONF = "toolchain.service.users.ui.urls"

INSTALLED_APPS.extend(USERS_DB_DJANGO_APPS + ("django.contrib.sessions", "toolchain.workflow.apps.WorkflowAppConfig"))
AUTH_USER_MODEL = "site.ToolchainUser"

set_up_databases(__name__, "users")

# The social_auth Django app uses a transaction block to create a user, and doesn't
# specify the db, so it uses `default`. Until we can fix this, allow that alias in the users service.
# Similar to code we have in service/users/admin/settings.py
# we check for dev/prod in order to avoid doing this when running certain commands (collect_static for example)
if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    DATABASES["default"] = DATABASES["users"]

REST_FRAMEWORK = get_rest_framework_config(with_permissions=False)
MIDDLEWARE = USERS_UI_MIDDLEWARE

# Session, cookie and CSRF settings.
# ----------------------------------

CSRF_TRUSTED_ORIGINS = [f"{'https' if TOOLCHAIN_ENV.is_prod else 'http'}://*.toolchain.com", "http://localhost"]  # type: ignore[attr-defined]
SESSION_COOKIE_AGE = int(datetime.timedelta(days=14 if TOOLCHAIN_ENV.is_dev else 7).total_seconds())  # type: ignore[attr-defined]

if TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_DOMAIN: str | None = ".toolchain.com"  # We want to share sessions across subdomains.


# Auth settings.
# --------------
SOCIAL_AUTH_REDIRECT_IS_HTTPS = TOOLCHAIN_ENV.is_prod  # type: ignore[attr-defined]

AUTHENTICATION_BACKENDS = (
    "toolchain.django.site.auth.toolchain_github.ToolchainGithubOAuth2",
    "toolchain.django.site.auth.toolchain_bitbucket.ToolchainBitbucketOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)

SECURE_HSTS_SECONDS = int(datetime.timedelta(days=180).total_seconds())
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

LOGIN_URL = get_login_url(TOOLCHAIN_ENV, config)
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
# See SocialAuthExceptionMiddleware.get_redirect_uri
LOGIN_ERROR_URL = SOCIAL_AUTH_LOGIN_ERROR_URL = URLNames.USER_ACCESS_DENIED
CSRF_USE_SESSIONS = True  # Used for the accept TOS flow

TEMPLATES = get_jinja2_template_config(add_csp_extension=True)

# See https://python-social-auth.readthedocs.io/en/latest/pipeline.html#authentication-pipeline.
SOCIAL_AUTH_PIPELINE = USERS_SOCIAL_AUTH_PIPELINE

SOCIAL_AUTH_JSONFIELD_ENABLED = True

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

if TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    TOOLCHAIN_GITHUB_APP_INSTALL_LINK = config["TOOLCHAIN_GITHUB_APP_INSTALL_LINK"]
elif TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    # In localdev we don't have this config, so it is fine to hard code it so local dev can work
    TOOLCHAIN_GITHUB_APP_INSTALL_LINK = config.get(
        "TOOLCHAIN_GITHUB_APP_INSTALL_LINK", "https://github.com/apps/toolchain-dev/installations/new"
    )
else:
    TOOLCHAIN_GITHUB_APP_INSTALL_LINK = "fake-value"

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    JWT_AUTH_KEY_DATA = JWTSecretData.read_settings(TOOLCHAIN_ENV, SECRETS_READER)
    SECRET_KEY = SECRETS_READER.get_secret_or_raise("django-secret-key")
    # GitHub app settings.
    _github_app_creds = SECRETS_READER.get_json_secret_or_raise("github-app-creds")
    SOCIAL_AUTH_GITHUB_KEY = _github_app_creds["GITHUB_KEY"]
    SOCIAL_AUTH_GITHUB_SECRET = _github_app_creds["GITHUB_SECRET"]
    SOCIAL_AUTH_GITHUB_SCOPE = ["user:email", "read:user", "read:org"]
    _bitbucket_oauth_creds = SECRETS_READER.get_json_secret_or_raise("bitbucket-oauth-creds")
    SOCIAL_AUTH_BITBUCKET_KEY = _bitbucket_oauth_creds["BITBUCKET_OAUTH_CLIENT_KEY"]
    SOCIAL_AUTH_BITBUCKET_SECRET = _bitbucket_oauth_creds["BITBUCKET_OAUTH_CLIENT_SECRET"]
    SOCIAL_AUTH_BITBUCKET_SCOPE = ["account", "email", "team"]
else:
    SECRET_KEY = "users-ui-fake-💼secret-🤖-key-👻"

TOS_VERSION = CURRENT_TOS_VERSION
