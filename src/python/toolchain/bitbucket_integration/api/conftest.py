# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.bitbucket_integration.config import AppDescriptor, BitbucketIntegrationConfig
from toolchain.bitbucket_integration.constants import BITBUCKET_INTEGRATION_DJANGO_APP
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP

_SETTINGS = dict(
    ROOT_URLCONF="toolchain.service.scm_integration.api.urls",
    UNAUTHENTICATED_USER=None,
    MIDDLEWARE=get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=False),
    REST_FRAMEWORK=get_rest_framework_config(with_permissions=False, UNAUTHENTICATED_USER=None),
    BITBUCKET_STORE_KEY_PREFIX="moles/freckles",
    SCM_INTEGRATION_BUCKET="fake-scm-integration-bucket",
    BITBUCKET_CONFIG=BitbucketIntegrationConfig(
        descriptor=AppDescriptor.for_dev(),
        client_id="ovaltine",
        secret="the bus boy is coming",
        install_link="https://jerry.hello.com/soup",
    ),
)


_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    BITBUCKET_INTEGRATION_DJANGO_APP,
    GITHUB_INTEGRATION_DJANGO_APP,
    "toolchain.workflow.apps.WorkflowAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
