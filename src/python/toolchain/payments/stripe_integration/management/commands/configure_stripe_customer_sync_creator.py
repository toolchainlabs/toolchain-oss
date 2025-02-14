# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.payments.stripe_integration.models import PeriodicallyCreateStripeCustomerSync


class Command(BaseCommand):
    help = (
        "Configures the workflow that checks for new customers and configure a Stripe Customer Sync workflow for them"
    )

    def handle(self, *args, **options) -> None:
        interval = options["interval_minutes"]
        PeriodicallyCreateStripeCustomerSync.create_or_update(period_minutes=interval)

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-minutes",
            type=int,
            required=False,
            default=10,  # Every 10m
            help="Check interval (minutes)",
        )
