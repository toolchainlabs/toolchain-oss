# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import Customer
from toolchain.payments.stripe_integration.models import SubscribedCustomer


def create_subscribed_customer(customer: Customer, payout_outside_stripe: bool = False) -> SubscribedCustomer:
    with freeze_time(utcnow() - datetime.timedelta(days=3)):  # so we can check/assert on SubscribedCustomer.modified
        sc = SubscribedCustomer.get_or_create(
            customer_id=customer.id, customer_slug=customer.slug, stripe_customer_id="newman"
        )
        sc.set_subscription_info("sub_jambalaya_soup", trial_end=None, plan="", plan_price_text="")
        if payout_outside_stripe:
            sc.payout_outside_of_stripe = True
            sc.save()

        return sc
