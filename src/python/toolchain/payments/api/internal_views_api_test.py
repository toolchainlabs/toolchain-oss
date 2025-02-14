# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.payments.amberflo_integration.models import AmberfloCustomerMTDMetrics
from toolchain.payments.stripe_integration.models import SubscribedCustomer


@pytest.mark.django_db()
class TestInternalPaymentsCustomerViewView:
    def test_get_plan_and_metrics(self, client) -> None:
        sc = SubscribedCustomer.get_or_create(customer_id="frank", customer_slug="costanza", stripe_customer_id="bob")
        sc.set_subscription_info(
            "chicken", trial_end=datetime.date(2023, 10, 3), plan="Festivus Mircale", plan_price_text="no soup for you"
        )
        AmberfloCustomerMTDMetrics.update_or_create(
            customer_id="frank",
            customer_slug="costanza",
            date=utcnow().date(),
            cache_read_bytes=111_000_506,
            cache_write_bytes=322_000_506,
        )
        response = client.get("/internal/api/v1/customers/frank/info/")
        assert response.status_code == 200
        assert response.json() == {
            "usage": {"read_bytes": 111000506, "write_bytes": 322000506},
            "plan": {"name": "Festivus Mircale", "price": "no soup for you", "trial_end": "2023-10-03"},
        }
