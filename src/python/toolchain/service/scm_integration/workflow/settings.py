# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

INSTALLED_APPS.extend(("django.contrib.auth", "toolchain.django.site", GITHUB_INTEGRATION_DJANGO_APP))
# For now stging, since we actually use a "dev" version of the GH app in prod
# Once integration and testing (in prod/staging) is done, we will move this to a prod URL & GH app
REPO_WEBHOOK_URL = "https://webhooks.toolchain.com/github/repo/"
TOOLCHAIN_WEBHOOK_EXPRESSION = re.compile(r"^https://.*\.toolchain.com/")

_common_github_stats_key_path = ("github", "statistics")
if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    GITHUB_STATS_STORE_KEY_PREFIX = os.path.join("dev", NAMESPACE, *_common_github_stats_key_path)
    SCM_INTEGRATION_BUCKET = config.get("SCM_INTEGRATION_BUCKET", "scm-integration-dev.us-east-1.toolchain.com")
elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    GITHUB_STATS_STORE_KEY_PREFIX = os.path.join("prod", "v1", *_common_github_stats_key_path)
    SCM_INTEGRATION_BUCKET = config["SCM_INTEGRATION_BUCKET"]

set_up_databases(__name__, "users", "scm_integration")


GITHUB_CONFIG = GithubIntegrationConfig.from_secrets_and_config(config, SECRETS_READER)
