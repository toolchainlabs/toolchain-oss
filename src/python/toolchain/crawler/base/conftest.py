# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config

_SETTINGS = dict(
    WEBRESOURCE_BUCKET="fake-web-resource-bucket",
    WEBRESOURCE_KEY_PREFIX="del/boca/vista",
    MAX_INLINE_TEXT_SIZE=3,
    INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT=True,
)

_APPS = [
    "toolchain.crawler.base.apps.CrawlerBaseAppConfig",
    "toolchain.django.webresource.apps.WebResourceAppConfig",
    "toolchain.workflow.apps.WorkflowAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
