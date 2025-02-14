# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.bitbucket_integration.constants import BITBUCKET_INTEGRATION_DJANGO_APP
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import (
    MiddlewareAuthMode,
    get_memory_cache,
    get_middleware,
    get_rest_framework_config,
)
from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP
from toolchain.util.test.crypto_utils import generate_private_key

_SETTINGS = dict(
    ROOT_URLCONF="toolchain.service.scm_integration.api.urls",
    SCM_INTEGRATION_BUCKET="fake-scm-integration-bucket",
    GITHUB_WEBHOOKS_STORE_KEY_PREFIX="lloyd/braun",
    TRAVIS_WEBHOOKS_STORE_KEY_PREFIX="bushmen/poppy/seed",
    UNAUTHENTICATED_USER=None,
    CACHE=get_memory_cache(location="scm-integration"),
    MIDDLEWARE=get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=False),
    REST_FRAMEWORK=get_rest_framework_config(with_permissions=False, UNAUTHENTICATED_USER=None),
    GITHUB_CONFIG=GithubIntegrationConfig(
        private_key=generate_private_key(), app_id="feats-of-strength", public_link="https://seinfeld.jerry.com/babka"
    ),
)

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    GITHUB_INTEGRATION_DJANGO_APP,
    BITBUCKET_INTEGRATION_DJANGO_APP,
    "toolchain.workflow.apps.WorkflowAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
