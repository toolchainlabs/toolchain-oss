# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config

_SETTINGS = dict(IS_RUNNING_ON_K8S=True, NAMESPACE="tinsel")


EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, [])


logging.config.dictConfig(get_logging_config())
