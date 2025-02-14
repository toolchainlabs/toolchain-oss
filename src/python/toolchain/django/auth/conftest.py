# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS

_APPS = ["toolchain.workflow.apps.WorkflowAppConfig"]
_APPS.extend(USERS_DB_DJANGO_APPS)

APPS_UNDER_TEST.extend(_APPS)


def pytest_configure():
    configure_settings({}, _APPS)


logging.config.dictConfig(get_logging_config())
