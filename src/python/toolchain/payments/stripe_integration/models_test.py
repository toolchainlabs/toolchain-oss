# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.payments.stripe_integration.models import PeriodicallySyncStripeCustomer, SubscribedCustomer
from toolchain.workflow.models import WorkUnit


@pytest.mark.django_db()
class TestSubscribedCustomerModel:
    def test_create_new(self) -> None:
        assert SubscribedCustomer.objects.count() == 0
        now_ts = utcnow().timestamp()
        sc = SubscribedCustomer.get_or_create(customer_id="jerry", customer_slug="puddy", stripe_customer_id="newman")
        assert SubscribedCustomer.objects.count() == 1
        loaded = SubscribedCustomer.objects.first()
        assert sc.customer_id == loaded.customer_id == "jerry"
        assert sc.customer_slug == loaded.customer_slug == "puddy"
        assert sc.stripe_customer_id == loaded.stripe_customer_id == "newman"
        assert sc.created == loaded.created
        assert sc.created.timestamp() == pytest.approx(now_ts)
        assert sc.stripe_subscription_id == loaded.stripe_subscription_id == ""
        assert sc.payout_outside_of_stripe is False

    def get_by_customer_id(self) -> None:
        sc = SubscribedCustomer.get_or_create(customer_id="jerry", customer_slug="puddy", stripe_customer_id="newman")
        assert SubscribedCustomer.get_by_customer_id("newman") is None
        loaded_sc = SubscribedCustomer.get_by_customer_id("jerry")
        assert loaded_sc is not None
        assert loaded_sc == sc
        assert loaded_sc.customer_id == "jerry"
        assert loaded_sc.customer_slug == "puddy"
        assert loaded_sc.stripe_customer_id == "newman"
        assert loaded_sc.stripe_subscription_id == ""
        assert loaded_sc.payout_outside_of_stripe is False

    def test_set_subscription_info(self, django_assert_num_queries) -> None:
        sc = SubscribedCustomer.get_or_create(customer_id="jerry", customer_slug="puddy", stripe_customer_id="newman")
        assert sc.stripe_subscription_id == ""
        with django_assert_num_queries(1):
            sc.set_subscription_info(
                "crazy_joe", trial_end=None, plan="Festivus Mircale", plan_price_text="no soup for you"
            )
        assert sc.stripe_subscription_id == "crazy_joe"
        loaded_sc = SubscribedCustomer.get_by_customer_id("jerry")
        assert loaded_sc is not None
        assert loaded_sc.stripe_subscription_id == "crazy_joe"
        assert loaded_sc.plan_name == "Festivus Mircale"
        assert loaded_sc.plan_price_text == "no soup for you"
        assert loaded_sc.trial_end is None
        assert loaded_sc.payout_outside_of_stripe is False

    def test_set_subscription_id_no_op(self, django_assert_num_queries) -> None:
        sc = SubscribedCustomer.get_or_create(customer_id="jerry", customer_slug="puddy", stripe_customer_id="newman")
        sc.set_subscription_info(
            "crazy_joe", trial_end=None, plan="Festivus Mircale", plan_price_text="no soup for you"
        )
        loaded_sc = SubscribedCustomer.get_by_customer_id("jerry")
        assert loaded_sc is not None
        with django_assert_num_queries(0):
            sc.set_subscription_info(
                "crazy_joe", trial_end=None, plan="Festivus Mircale", plan_price_text="no soup for you"
            )

    def test_set_subscription_id_invalid_id(self, django_assert_num_queries) -> None:
        sc = SubscribedCustomer.get_or_create(customer_id="jerry", customer_slug="puddy", stripe_customer_id="newman")
        assert sc.stripe_subscription_id == ""
        with django_assert_num_queries(0), pytest.raises(ToolchainAssertion, match="Invalid subscription_id"):
            sc.set_subscription_info("", trial_end=None, plan="Festivus Mircale", plan_price_text="no soup for you")

    def test_force_update(self, django_assert_num_queries) -> None:
        base_time = utcnow() - datetime.timedelta(days=3)
        with freeze_time(base_time):
            sc = SubscribedCustomer.get_or_create(
                customer_id="puddy", customer_slug="puddy", stripe_customer_id="newman"
            )
        assert sc.created == sc.modified == base_time
        with django_assert_num_queries(1):
            sc.force_updated()
        assert sc.modified > base_time
        assert sc.modified.timestamp() == pytest.approx(utcnow().timestamp())


@pytest.mark.django_db()
class TestPeriodicallySyncStripeCustomerModel:
    def test_create(self) -> None:
        assert PeriodicallySyncStripeCustomer.objects.count() == 0
        PeriodicallySyncStripeCustomer.get_or_create(customer_id="newman", customer_slug="hello")
        assert PeriodicallySyncStripeCustomer.objects.count() == 1
        pssc = PeriodicallySyncStripeCustomer.objects.first()
        assert pssc.customer_id == "newman"
        assert pssc.customer_slug == "hello"
        assert pssc.work_unit.state == WorkUnit.READY

    def test_get_existing(self) -> None:
        PeriodicallySyncStripeCustomer.get_or_create(customer_id="newman", customer_slug="hello")
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        now = utcnow()
        wu.take_lease(until=now + datetime.timedelta(minutes=20), last_attempt=now, node="happy-festivus")
        wu.work_succeeded(False)
        assert wu.state == WorkUnit.SUCCEEDED

        PeriodicallySyncStripeCustomer.get_or_create(customer_id="newman", customer_slug="jerry")
        assert PeriodicallySyncStripeCustomer.objects.count() == 1
        pssc = PeriodicallySyncStripeCustomer.objects.first()
        assert pssc.customer_slug == "jerry"
        assert pssc.work_unit.state == WorkUnit.SUCCEEDED
