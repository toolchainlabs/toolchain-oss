# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import logging

import stripe
from django.core.management.base import BaseCommand

from toolchain.payments.stripe_integration.models import SubscribedCustomer

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set billing cycle anchor for existing subscriptions."

    def handle(self, *args, **options) -> None:
        dry_run = not options["no_dry_run"]
        customer_slug = options["customer"]
        sc = SubscribedCustomer.objects.get(customer_slug=customer_slug)
        subscription = stripe.Subscription.retrieve(id=sc.stripe_subscription_id)
        current_billing_cycle_anchor = datetime.datetime.fromtimestamp(
            subscription.billing_cycle_anchor, tz=datetime.timezone.utc
        ).isoformat()
        _logger.info(f"{sc}  {current_billing_cycle_anchor=} {subscription.status=} {dry_run=}")
        if not dry_run:
            stripe.Subscription.modify(sid=sc.stripe_subscription_id, billing_cycle_anchor="now")

    def add_arguments(self, parser):
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument("--customer", required=True, help="Customer slug")
