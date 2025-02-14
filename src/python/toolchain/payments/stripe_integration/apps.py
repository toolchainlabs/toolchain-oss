# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class StripeIntegrationApp(AppConfig):
    name = "toolchain.payments.stripe_integration"
    label = "stripe_integration"
    verbose_name = "Stripe Integration App"
