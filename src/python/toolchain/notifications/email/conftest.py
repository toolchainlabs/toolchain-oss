# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config
from pathlib import Path

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    "toolchain.notifications.email.apps.EmailAppConfig",
    "toolchain.workflow.apps.WorkflowAppConfig",
]

_SETTINGS = dict(
    RENDER_EMAIL_S3_BUCKET="del-boca-vista-bucket",
    RENDER_EMAIL_S3_BASE_PATH=Path("test/jerry/emails/"),
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
