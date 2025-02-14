# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.payments.stripe_integration.stripe_init import init_stripe

set_up_databases(__name__, "payments", "users")
CSRF_USE_SESSIONS = False
# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"👻payments💀api👽{uuid.uuid4()}☠️👾"
MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=False)
ROOT_URLCONF = "toolchain.service.payments.api.urls"
AUTH_USER_MODEL = "site.ToolchainUser"
REST_FRAMEWORK = get_rest_framework_config(with_permissions=False, UNAUTHENTICATED_USER=None)
INSTALLED_APPS = list(COMMON_APPS)
INSTALLED_APPS.extend(
    (
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.workflow.apps.WorkflowAppConfig",
        "toolchain.payments.stripe_integration.apps.StripeIntegrationApp",
        "toolchain.payments.amberflo_integration.apps.AmberfloIntegrationApp",
    )
)
if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    init_stripe(tc_env=TOOLCHAIN_ENV, secrets_reader=SECRETS_READER)
