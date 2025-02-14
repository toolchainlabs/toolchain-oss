# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.bitbucket_integration.constants import BITBUCKET_INTEGRATION_DJANGO_APP
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config

_SETTINGS = dict(
    BITBUCKET_STORE_KEY_PREFIX="moles/freckles",
    SCM_INTEGRATION_BUCKET="fake-scm-integration-bucket",
)

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    BITBUCKET_INTEGRATION_DJANGO_APP,
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
