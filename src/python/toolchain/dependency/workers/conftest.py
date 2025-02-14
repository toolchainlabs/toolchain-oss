# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config

_APPS = [
    "toolchain.dependency.apps.DependencyAPIAppConfig",
    "toolchain.workflow.apps.WorkflowAppConfig",
]
_SETTINGS = dict(DRY_RUN_WORKFLOW_RESOLVE=False)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
