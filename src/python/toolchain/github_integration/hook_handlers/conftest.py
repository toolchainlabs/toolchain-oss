# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP

_SETTINGS = dict(
    SCM_INTEGRATION_BUCKET="fake-scm-integration-bucket",
    GITHUB_WEBHOOKS_STORE_KEY_PREFIX="jerry/hooks/festivs",
)

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    GITHUB_INTEGRATION_DJANGO_APP,
    "toolchain.workflow.apps.WorkflowAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
