# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config

CSRF_USE_SESSIONS = False
# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"👽notifications👻api💀{uuid.uuid4()}☠️👾"
MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=False)
ROOT_URLCONF = "toolchain.service.notifications.api.urls"
AUTH_USER_MODEL = "site.ToolchainUser"
REST_FRAMEWORK = get_rest_framework_config(with_permissions=False, UNAUTHENTICATED_USER=None)
INSTALLED_APPS = list(COMMON_APPS)
INSTALLED_APPS.extend(
    (
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.workflow.apps.WorkflowAppConfig",
        "toolchain.notifications.email.apps.EmailAppConfig",
    )
)

set_up_databases(__name__, "notifications", "users")
