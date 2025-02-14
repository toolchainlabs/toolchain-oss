# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.payments.amberflo_integration.config import AmberFloConfiguration
from toolchain.payments.stripe_integration.config import StripeConfiguration

_SETTINGS = dict(
    AMBERFLO_CONFIG=AmberFloConfiguration(api_key="yoyoma", env_name="jambalaya"),
    STRIPE_CONFIG=StripeConfiguration(trial_price_id="festivus", trial_period_days=5),
)

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    "toolchain.workflow.apps.WorkflowAppConfig",
    "toolchain.payments.stripe_integration.apps.StripeIntegrationApp",
    "toolchain.payments.amberflo_integration.apps.AmberfloIntegrationApp",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
