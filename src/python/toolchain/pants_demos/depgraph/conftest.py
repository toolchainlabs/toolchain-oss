# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware
from toolchain.django.spa.config import StaticContentConfig
from toolchain.pants_demos.depgraph.constants import TEMPLATES_CONFIG

_APPS = [
    "toolchain.workflow.apps.WorkflowAppConfig",
    "toolchain.pants_demos.depgraph.apps.PantsDepgraphDemoApp",
    "django.contrib.sitemaps",
]

_SETTINGS = dict(
    STATIC_URL="/static/",
    MIDDLEWARE=get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=True),
    ROOT_URLCONF="toolchain.service.pants_demos.depgraph.web.urls",
    TEMPLATES=TEMPLATES_CONFIG,
    STATIC_CONTENT_CONFIG=StaticContentConfig.for_test(),
    JS_SENTRY_DSN="https://fake-sentry.jerry.crazy.joe-davola.net/opera",
    REPOS_DISABLE_INDEXING=frozenset(("cosmo/kramer", "usps/newman")),
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)

APPS_UNDER_TEST.extend(_APPS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
