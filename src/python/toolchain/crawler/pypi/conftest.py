# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.crawler.pypi.constants import APPS
from toolchain.django.site.logging.logging_helpers import get_logging_config

_APPS = APPS + ["toolchain.workflow.apps.WorkflowAppConfig"]

_SETTINGS = dict(
    WEBRESOURCE_BUCKET="jambalaya",
    WEBRESOURCE_KEY_PREFIX="seinfeld/no-soup-for-you",
    INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT=True,
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
