# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import copy
import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings, configure_test_databases
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware
from toolchain.toolshed.config import AuthCookieConfig, DuoAuthConfig
from toolchain.toolshed.constants import (
    ADMIN_APPS,
    ADMIN_DBS,
    DEV_ONLY_ADMIN_APPS,
    DEV_ONLY_ADMIN_DBS,
    DJANGO_TEMPLATE_CONFIG,
    TOOLSHED_MIDDLEWARE,
)
from toolchain.toolshed.db_router import RequestContextDBRouter

_APPS = ADMIN_APPS + DEV_ONLY_ADMIN_APPS


def _toolshed_test_dbs():
    all_dbs = ADMIN_DBS + DEV_ONLY_ADMIN_DBS
    db_configs = configure_test_databases(*all_dbs)
    default_db = copy.deepcopy(db_configs["users"])
    default_db["TEST"]["MIRROR"] = "users"
    db_configs["default"] = default_db
    return db_configs


_SETTINGS = dict(
    ALLOWED_HOSTS=["no-soup-for-you.seinfeld"],
    ROOT_URLCONF="toolchain.toolshed.urls",
    STATIC_URL="/static/",  # Needed for correctly loading jinja2 templates in tests.
    TEMPLATES=[DJANGO_TEMPLATE_CONFIG] + get_jinja2_template_config(),
    MIDDLEWARE=get_middleware(
        auth_mode=MiddlewareAuthMode.DJANGO,
        with_csp=False,
        append_middleware=TOOLSHED_MIDDLEWARE,
    ),
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AUTH_COOKIE_CONFIG=AuthCookieConfig.for_tests(),
    SESSION_COOKIE_DOMAIN=None,
    DUO_CONFIG=DuoAuthConfig(
        secret_key="stay-away-from-the-chicken-bad-chicken-mess-you-up"[:40],
        application_key="quit-telling-your-stupid-story-about-the-stupid-desert"[:20],
        host="cosmo.kramer.private",
    ),
    DATABASES=_toolshed_test_dbs(),
    DATABASE_ROUTERS=[RequestContextDBRouter("toolshed")],
    MAIN_SITE_PREFIX="https://games.com.au",
)

APPS_UNDER_TEST.extend(_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
