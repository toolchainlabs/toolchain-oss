# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import get_memory_cache
from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP
from toolchain.util.test.crypto_utils import generate_private_key

_FAKE_PRIVATE_KEY = generate_private_key()

_SETTINGS = dict(
    REPO_WEBHOOK_URL="http://jerry.com/dave/repo",
    GITHUB_CONFIG=GithubIntegrationConfig(
        private_key=generate_private_key(), app_id="bosco", public_link="https://babka.jerry/dinner"
    ),
    SCM_INTEGRATION_BUCKET="fake-scm-integration-bucket",
    GITHUB_STATS_STORE_KEY_PREFIX="fake-github-stats",
    GITHUB_WEBHOOKS_STORE_KEY_PREFIX="lloyd/braun",
    TRAVIS_WEBHOOKS_STORE_KEY_PREFIX="poppy/seed",
    CACHE=get_memory_cache(location="scm-integration"),
)

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    GITHUB_INTEGRATION_DJANGO_APP,
    "toolchain.workflow.apps.WorkflowAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
