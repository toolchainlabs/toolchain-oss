# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.spa.config import StaticContentConfig
from toolchain.servicerouter.settings import LOGIN_URL, SERVICE_ROUTER_MIDDLEWARE, TEMPLATES_CFG
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.users.jwt.keys import JWTSecretData

_APPS = [
    "toolchain.workflow.apps.WorkflowAppConfig",
    "toolchain.servicerouter.apps.ServiceRouterAppConfig",
]

_APPS.extend(USERS_DB_DJANGO_APPS)

_SETTINGS = dict(
    LOGIN_URL=LOGIN_URL,
    ROOT_URLCONF="toolchain.servicerouter.urls",
    STATIC_URL="/static/",  # Needed for correctly loading jinja2 templates in tests.
    TEMPLATES=TEMPLATES_CFG,
    MIDDLEWARE=SERVICE_ROUTER_MIDDLEWARE,
    CSP_INCLUDE_NONCE_IN=("script-src",),
    IS_RUNNING_ON_K8S=False,
    NAMESPACE="jambalaya",
    STATIC_CONTENT_CONFIG=StaticContentConfig.for_test(),
    JS_SENTRY_DSN="https://gold.jerry.local",
    JWT_AUTH_KEY_DATA=JWTSecretData.create_for_tests_identical("He stopped short"),
    IS_TOOLCHAIN_DJANGO_TESTS=True,
    TOOLCHAIN_GITHUB_APP_INSTALL_LINK="https://no-soup-for-you.jerrt.com/pole/install/",
)

APPS_UNDER_TEST.extend(_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
