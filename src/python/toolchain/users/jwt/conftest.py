# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.config.helpers import get_login_url
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.constants import ToolchainEnv
from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.users.jwt.config import JWTConfig
from toolchain.users.jwt.keys import JWTSecretData
from toolchain.util.config.app_config import AppConfig

_APPS = ["toolchain.workflow.apps.WorkflowAppConfig"]
_APPS.extend(USERS_DB_DJANGO_APPS)
_SETTINGS = dict(
    STATIC_URL="/static/",
    TEMPLATES=get_jinja2_template_config(add_csp_extension=True),
    MIDDLEWARE=get_middleware(auth_mode=MiddlewareAuthMode.INTERNAL, with_csp=True),
    JWT_AUTH_KEY_DATA=JWTSecretData.create_for_tests("it's not you, its me", base_key_id="tinsel"),
    REST_FRAMEWORK=get_rest_framework_config(),
    ROOT_URLCONF="toolchain.service.users.api.urls",
    # Because we now call the GH integration service API
    IS_RUNNING_ON_K8S=True,
    NAMESPACE="tinsel",
    LOGIN_URL=get_login_url(ToolchainEnv.DEV, AppConfig({})),  # type: ignore[attr-defined]
    TOOLCHAIN_REMOTE_CACHE_ADDRESS="grpcs://jerry.happy.festivus:443",
    TOOLCHAIN_GITHUB_APP_INSTALL_LINK="https://no-soup-for-you.jerrt.com/pole/install/",
    ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS=frozenset(["seinfeld"]),
    JWT_CONFIG=JWTConfig.for_dev(),
)

APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
