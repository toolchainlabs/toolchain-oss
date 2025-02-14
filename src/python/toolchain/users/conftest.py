# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.users.jwt.keys import JWTSecretData

_APPS = ["toolchain.workflow.apps.WorkflowAppConfig"]

_APPS.extend(USERS_DB_DJANGO_APPS)
# Settings for the users/api services.
_SETTINGS = dict(
    REST_FRAMEWORK=get_rest_framework_config(),
    STATIC_URL="/static/",
    JWT_AUTH_KEY_DATA=JWTSecretData.create_for_tests_identical("it's not you, its me"),
    ROOT_URLCONF="toolchain.service.users.api.urls",
    IS_RUNNING_ON_K8S=True,
    NAMESPACE="tinsel",
    MIDDLEWARE=get_middleware(auth_mode=MiddlewareAuthMode.INTERNAL, with_csp=True),
    TEMPLATES=get_jinja2_template_config(add_csp_extension=True),
    CSRF_USE_SESSIONS=False,
    TOS_VERSION="jerry-2022",
    ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS=frozenset(["acmeid", "davola"]),
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
