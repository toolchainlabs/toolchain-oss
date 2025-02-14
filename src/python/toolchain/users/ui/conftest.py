# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import get_rest_framework_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.users.jwt.keys import JWTSecretData
from toolchain.users.ui.constants import USERS_SOCIAL_AUTH_PIPELINE, USERS_UI_MIDDLEWARE, USERS_UI_URLS
from toolchain.users.ui.url_names import URLNames

_APPS = [
    "django.contrib.sessions",
    "toolchain.workflow.apps.WorkflowAppConfig",
]
_APPS.extend(USERS_DB_DJANGO_APPS)

_SETTINGS = dict(
    REST_FRAMEWORK=get_rest_framework_config(),
    STATIC_URL="/static/",
    LOGIN_REDIRECT_URL="/",
    LOGOUT_REDIRECT_URL="/",
    LOGIN_ERROR_URL=URLNames.USER_ACCESS_DENIED,
    SOCIAL_AUTH_LOGIN_ERROR_URL=URLNames.USER_ACCESS_DENIED,
    SOCIAL_AUTH_PIPELINE=USERS_SOCIAL_AUTH_PIPELINE,
    JWT_AUTH_KEY_DATA=JWTSecretData.create_for_tests_identical("it's not you, its me"),
    ROOT_URLCONF=USERS_UI_URLS,
    IS_RUNNING_ON_K8S=True,
    NAMESPACE="tinsel",
    CSRF_USE_SESSIONS=True,
    MIDDLEWARE=USERS_UI_MIDDLEWARE,
    TEMPLATES=get_jinja2_template_config(add_csp_extension=True),
    TOS_VERSION="hello-newman-2022",
    TOOLCHAIN_GITHUB_APP_INSTALL_LINK="https://no-soup-for-you.jerrt.com/pole/install/",
    AUTHENTICATION_BACKENDS=(
        "toolchain.django.site.auth.toolchain_github.ToolchainGithubOAuth2",
        "toolchain.django.site.auth.toolchain_bitbucket.ToolchainBitbucketOAuth2",
        "django.contrib.auth.backends.ModelBackend",
    ),
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
