# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config
import re

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP
from toolchain.util.test.crypto_utils import generate_private_key

_FAKE_PRIVATE_KEY = generate_private_key()

_SETTINGS = dict(
    GITHUB_CONFIG=GithubIntegrationConfig(
        private_key=generate_private_key(), app_id="bosco", public_link="https://babka.jerry/dinner"
    ),
    REPO_WEBHOOK_URL="http://newman.jerry.com/dave/repo",
    TOOLCHAIN_WEBHOOK_EXPRESSION=re.compile(r"^http://.*\.jerry.com/"),
    GITHUB_STATS_STORE_KEY_PREFIX="fake-github-stats",
    SCM_INTEGRATION_BUCKET="fake-scm-integration-bucket",
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
