# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

import pytest
import stripe

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.payments.stripe_integration.config import StripeConfiguration


@pytest.fixture(autouse=True)
def _fake_stripe_init() -> None:
    stripe.api_key = "no-soup-for-you"
    # also in stripe_client_test.py
    stripe.api_base = "https://jerry.not-stripe.fake"


_SETTINGS = dict(
    ROOT_URLCONF="toolchain.service.payments.api.urls",
    STRIPE_CONFIG=StripeConfiguration(trial_price_id="festivus", trial_period_days=5),
    IS_RUNNING_ON_K8S=True,
    NAMESPACE="tinsel",
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
