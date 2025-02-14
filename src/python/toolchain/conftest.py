# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Collection
from typing import Any

import pytest
import shortuuid
from django.conf import settings
from django.core.cache import cache

from toolchain.aws.aws_api import AWSService
from toolchain.aws.test_utils.common import TEST_REGION
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ServiceLocation, ToolchainEnv, ToolchainServiceInfo, ToolchainServiceType
from toolchain.testing_db import TestingDB

# Pytest configuration.

# Pytest auto-configures based on hooks in conftest.py.

# Note that, to be discovered, this file must be in a parent directory of the test code.
# Which is why it's directly under src/python/toolchain.


_COMMON_MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "toolchain.django.site.middleware.request_middleware.ToolchainRequestMiddleware",
    "toolchain.django.site.middleware.error_middleware.TransientErrorsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

_COMMON_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_prometheus",
)
# Lower-level conftest.py files can append to this to inform this top-level conftest.py
# that these apps need to be loaded.
APPS_UNDER_TEST: list[str] = []


# Lower-level conftest.py files can call this to cause database to be set up.
# A database will always be set up if there are any APPS_UNDER_TEST, regardless of this setting.


def configure_empty_test_db():
    TestingDB.create()


def testing_db_host_port():
    """The [host, port] for the testing db.

    Useful for non-Django tests.

    Note that name does not start with test_, so that this function doesn't get discovered as a test by pytest.
    """
    return TestingDB.DB_HOST_PORT


# Lower-level conftest.py files can add to this to inform this top-level conftest.py
# that Django needs to be configured with these extra settings.
EXTRA_SETTINGS: dict[str, Any] = {}


# We can specify custom migration modules and, in particular, `None` to disable migrations:
#   https://docs.djangoproject.com/en/2.2/ref/settings/#migration-modules
# This custom dict ensures we'll answer "no migrations" for all models whatever.
class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


@pytest.fixture(autouse=True)
def _disable_real_aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "fake-aws-creds-key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-aws-creds-access-key")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "fake-aws-creds-session-token")


def pytest_configure():
    configure_settings(EXTRA_SETTINGS, APPS_UNDER_TEST)


@pytest.fixture(autouse=True)
def _django_autoclear_cache(settings) -> None:
    cache.clear()


def configure_test_databases(*db_names: str) -> dict[str, dict]:
    test_db = TestingDB.create()
    return {name: get_test_db_config(test_db, name) for name in db_names}


def get_test_db_config(test_db: TestingDB, db_name: str) -> dict:
    return {
        "ENGINE": "django.db.backends.postgresql",
        # Note that this config is only used in test contexts, so the db NAME for testing is taken from the
        # 'TEST' dict below. However the "production" NAME must still point to an existing db, or Django
        # startup checks will fail.
        "NAME": "postgres",
        "USER": "postgres",
        "HOST": test_db.host,
        "PORT": test_db.port,
        "TEST": {
            "DEPENDENCIES": [],
            # NB: We use a random UUID to ensure that tests run concurrently (i.e. through the V2 test
            # runner) do not share the same database name.
            "NAME": f"testdb_{db_name}_{shortuuid.uuid()}",
        },
    }


def configure_settings(extra_settings: dict, apps_under_test: Collection[str], add_common_apps: bool = True) -> None:
    if settings.configured:
        return

    if len(set(apps_under_test)) != len(apps_under_test):
        raise ToolchainAssertion(f"Duplicate apps in {apps_under_test}")

    # if the application is already in _COMMON_APPS then remove it from APPS_UNDER_TEST/deduped_apps_under_test
    if add_common_apps:
        apps_under_test_copy = list(apps_under_test)
        for app_name in set(_COMMON_APPS).intersection(set(apps_under_test)):
            apps_under_test_copy.remove(app_name)
        installed_apps = _COMMON_APPS + tuple(apps_under_test_copy)
    else:
        installed_apps = tuple(apps_under_test)

    extra_settings.setdefault(
        "SERVICE_INFO",
        ToolchainServiceInfo(name="fake-tc-service", _type=ToolchainServiceType.API, location=ServiceLocation.INTERNAL),
    )
    if "toolchain.django.site" in installed_apps:
        extra_settings.setdefault("AUTH_USER_MODEL", "site.ToolchainUser")
    extra_settings.setdefault("MIDDLEWARE", _COMMON_MIDDLEWARE)
    # For unit tests, to avoid dealing with secrets, we use the postgres user, which has passwordless access
    # to everything, and we let all db queries route to the `default` db, for simplicity.
    if extra_settings.get("DATABASES") is None:
        test_db = TestingDB.create()
        extra_settings["DATABASES"] = {"default": get_test_db_config(test_db, "default")}

    extra_settings.setdefault("DATABASE_ROUTER_REGISTRY", None)

    # Note that we can't do this directly in lower-level conftest.py files, because Django errors if
    # you call settings.configure() more than once.
    settings.configure(
        # moto requires a real region, even though it mocks out all the calls.
        # To avoid confusion, we pick one we're not currently using for prod.
        AWS_REGION=TEST_REGION,
        TOOLCHAIN_ENV=ToolchainEnv.TEST,  # type: ignore
        SECRET_KEY="TEST_SECRET_KEY",
        TIME_ZONE="UTC",
        USE_TZ=True,
        PROFILE=False,
        # Standard apps that we always (or almost always) need, plus the ones explicitly specified.
        INSTALLED_APPS=installed_apps,
        MIGRATION_MODULES=DisableMigrations(),
        **extra_settings,
    )
    AWSService.set_default_config(settings.AWS_REGION, {})
