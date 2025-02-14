# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config

_APPS = [
    "toolchain.packagerepo.pypi.apps.PackageRepoPypiAppConfig",
    "toolchain.django.webresource.apps.WebResourceAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)


def pytest_configure():
    configure_settings({}, _APPS)


logging.config.dictConfig(get_logging_config())
