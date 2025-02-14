# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.bitbucket_integration.config import BitbucketIntegrationConfig
from toolchain.bitbucket_integration.constants import BITBUCKET_INTEGRATION_DJANGO_APP
from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import (
    MiddlewareAuthMode,
    get_memory_cache,
    get_middleware,
    get_rest_framework_config,
)
from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP

set_up_databases(__name__, "scm_integration", "users")
CSRF_USE_SESSIONS = False
# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"scm👻integration💀api👽{uuid.uuid4()}☠️👾"
MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=False)
ROOT_URLCONF = "toolchain.service.scm_integration.api.urls"
AUTH_USER_MODEL = "site.ToolchainUser"
REST_FRAMEWORK = get_rest_framework_config(with_permissions=False, UNAUTHENTICATED_USER=None)
INSTALLED_APPS = list(COMMON_APPS)
INSTALLED_APPS.extend(
    (
        "django.contrib.auth",
        "toolchain.django.site",
        GITHUB_INTEGRATION_DJANGO_APP,
        BITBUCKET_INTEGRATION_DJANGO_APP,
        "toolchain.workflow.apps.WorkflowAppConfig",
    )
)

_common_github_stats_key_path = ("github", "statistics")
_common_github_webhooks_key_path = ("github", "webhooks")
_common_travis_webhooks_key_path = ("travis", "webhooks")

CACHE = get_memory_cache(location="scm-integration")
if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    SCM_INTEGRATION_BUCKET = config.get("SCM_INTEGRATION_BUCKET", "scm-integration-dev.us-east-1.toolchain.com")
    GITHUB_STATS_STORE_KEY_PREFIX = os.path.join("dev", NAMESPACE, *_common_github_stats_key_path)
    GITHUB_WEBHOOKS_STORE_KEY_PREFIX = os.path.join("dev", NAMESPACE, *_common_github_webhooks_key_path)
    TRAVIS_WEBHOOKS_STORE_KEY_PREFIX = os.path.join("dev", NAMESPACE, *_common_travis_webhooks_key_path)
    BITBUCKET_STORE_KEY_PREFIX = os.path.join("dev", NAMESPACE, "bitbucket")
elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    SCM_INTEGRATION_BUCKET = config["SCM_INTEGRATION_BUCKET"]
    GITHUB_STATS_STORE_KEY_PREFIX = os.path.join("prod", "v1", *_common_github_stats_key_path)
    GITHUB_WEBHOOKS_STORE_KEY_PREFIX = os.path.join("prod", "v1", *_common_github_webhooks_key_path)
    TRAVIS_WEBHOOKS_STORE_KEY_PREFIX = os.path.join("prod", "v1", *_common_travis_webhooks_key_path)
    BITBUCKET_STORE_KEY_PREFIX = os.path.join("prod", "v1", "bitbucket")

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    GITHUB_CONFIG = GithubIntegrationConfig.from_secrets_and_config(config, SECRETS_READER)
    BITBUCKET_CONFIG = BitbucketIntegrationConfig.from_secrets_and_config(
        tc_env=TOOLCHAIN_ENV, config=config, secrets_reader=SECRETS_READER
    )

BOTO3_CONFIG = {
    "s3": {
        "read_timeout": 2,
        "connect_timeout": 2,
    }
}
