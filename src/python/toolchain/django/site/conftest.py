# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.util.secret import secrets_accessor_factories

_APPS = [
    "toolchain.workflow.apps.WorkflowAppConfig",
]
_APPS.extend(USERS_DB_DJANGO_APPS)

_SETTINGS = dict(SECRETS_READER=secrets_accessor_factories.test_secrets_reader())

APPS_UNDER_TEST.extend(_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
