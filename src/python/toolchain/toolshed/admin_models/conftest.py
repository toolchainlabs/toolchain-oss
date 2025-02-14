# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.toolshed.constants import ADMIN_APPS, DEV_ONLY_ADMIN_APPS

_APPS = ADMIN_APPS + DEV_ONLY_ADMIN_APPS
APPS_UNDER_TEST.extend(_APPS)


def pytest_configure():
    configure_settings({}, _APPS)


logging.config.dictConfig(get_logging_config())
