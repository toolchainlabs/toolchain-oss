# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.infosite.constants import INFOSITE_APPS, INFOSITE_MIDDLEWARE

_SETTINGS = dict(
    ROOT_URLCONF="toolchain.infosite.urls",
    STATIC_URL="/static/",
    TEMPLATES=get_jinja2_template_config(add_csp_extension=True),
    MIDDLEWARE=INFOSITE_MIDDLEWARE,
    SECURE_REFERRER_POLICY="origin",
    DATABASES={},
)

APPS_UNDER_TEST.extend(INFOSITE_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, INFOSITE_APPS, add_common_apps=False)


logging.config.dictConfig(get_logging_config())
