# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.users.jwt.keys import JWTSecretData

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    "toolchain.django.webresource",
    "toolchain.packagerepo.pypi",
    "toolchain.dependency.apps.DependencyAPIAppConfig",
    "toolchain.workflow.apps.WorkflowAppConfig",
]
_SETTINGS = dict(
    MIDDLEWARE=get_middleware(auth_mode=MiddlewareAuthMode.INTERNAL, with_csp=False),
    JWT_AUTH_KEY_DATA=JWTSecretData.create_for_tests_identical("it's not you, its me"),
    REST_FRAMEWORK=get_rest_framework_config(),
    ROOT_URLCONF="toolchain.dependency.api.urls",
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
