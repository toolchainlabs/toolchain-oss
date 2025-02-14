# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.django.site.settings.service import *  # noqa: F40
from toolchain.payments.amberflo_integration.config import AmberFloConfiguration
from toolchain.payments.stripe_integration.config import StripeConfiguration
from toolchain.payments.stripe_integration.stripe_init import init_stripe
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

INSTALLED_APPS.extend(
    (
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.payments.stripe_integration.apps.StripeIntegrationApp",
        "toolchain.payments.amberflo_integration.apps.AmberfloIntegrationApp",
    )
)
AUTH_USER_MODEL = "site.ToolchainUser"

# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"🥉payments{uuid.uuid4()}☠️👾"

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    init_stripe(tc_env=TOOLCHAIN_ENV, secrets_reader=SECRETS_READER)
    STRIPE_CONFIG = StripeConfiguration.from_config(config, toolchain_env=TOOLCHAIN_ENV)
    AMBERFLO_CONFIG = AmberFloConfiguration.create(toolchain_env=TOOLCHAIN_ENV, secrets_reader=SECRETS_READER)

set_up_databases(__name__, "users", "payments")
