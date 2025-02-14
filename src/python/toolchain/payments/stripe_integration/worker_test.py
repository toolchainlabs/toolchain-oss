# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from dateutil import relativedelta

from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import Customer
from toolchain.payments.stripe_integration.models import (
    PeriodicallyCreateStripeCustomerSync,
    PeriodicallySyncStripeCustomer,
    SubscribedCustomer,
)
from toolchain.payments.stripe_integration.test_utils.model_utils import create_subscribed_customer
from toolchain.payments.stripe_integration.test_utils.utils import (
    add_create_customer_response,
    add_create_customer_subscriptions_response,
    add_get_subscription_response,
    add_list_customer_subscriptions_response,
    add_modify_customer_response,
    add_product_and_prices_responses,
    add_search_customer_empty_response,
    add_search_customer_response,
    assert_create_customer_subscriptions_request,
    assert_customer_create_request,
    assert_customer_search_request,
    assert_get_subscriptions_request,
    assert_list_customer_subscriptions_request,
    assert_modify_customer,
    assert_price_retrieve_request,
    assert_product_retrieve_request,
)
from toolchain.service.payments.workflow.dispatcher import PaymentsWorkDispatcher
from toolchain.users.client.user_client_test import add_get_admin_users_response
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests
from toolchain.workflow.work_dispatcher import WorkDispatcher
from toolchain.workflow.work_dispatcher_test import mark_work_unit_success


class BaseWorkerTests(BaseWorkflowWorkerTests):
    def get_dispatcher(self) -> type[WorkDispatcher]:
        return PaymentsWorkDispatcher


class TestPantsTPeriodicStripeCustomerSyncer(BaseWorkerTests):
    @pytest.fixture()
    def customer(self) -> Customer:
        # Using Customer.Type.CUSTOMER here to ensure we change into PROSPECT when we create a trial subscription.
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc.", customer_type=Customer.Type.CUSTOMER)

    @pytest.fixture()
    def prospect(self) -> Customer:
        return Customer.create(slug="usps", name="Postal Service", customer_type=Customer.Type.PROSPECT)

    def _assert_product_and_price_requests(self, responses, reqs: tuple[int, int] = (-2, -1)) -> None:
        assert_product_retrieve_request(responses.calls[reqs[0]].request, product_id="prod_LcgVoYRbtZeS7i")
        assert_price_retrieve_request(responses.calls[reqs[1]].request, price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF")

    def test_sync_new_customer(self, responses, httpx_mock, customer: Customer) -> None:
        assert SubscribedCustomer.objects.count() == 0
        add_search_customer_empty_response(responses)
        add_list_customer_subscriptions_response(responses, empty=True)
        add_create_customer_subscriptions_response(responses, stripe_customer_id="cus_newman")
        add_create_customer_response(responses, stripe_id="cus_newman", customer_id=customer.id)
        add_get_admin_users_response(httpx_mock, customer_id=customer.id, admins=(("david", "david@puddy.org"),))
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )

        first_billing_month = utcnow().date() + datetime.timedelta(days=5) + relativedelta.relativedelta(months=1)
        billing_anchor_ts = datetime.datetime(
            year=first_billing_month.year, month=first_billing_month.month, day=1, tzinfo=datetime.timezone.utc
        ).timestamp()
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 6
        assert_customer_search_request(responses.calls[0].request, "test", toolchain_customer_id=customer.id)
        assert_customer_create_request(
            responses.calls[1].request,
            "test",
            toolchain_customer_id=customer.id,
            name="Jerry Seinfeld Inc.",
            email="david@puddy.org",
        )
        assert_list_customer_subscriptions_request(responses.calls[2].request, stripe_customer_id="cus_newman")
        assert_create_customer_subscriptions_request(
            responses.calls[3].request,
            stripe_customer_id="cus_newman",
            toolchain_customer_id=customer.id,
            price_id="festivus",
            trial_period_days=5,
            billing_anchor_ts=int(billing_anchor_ts),
        )
        self._assert_product_and_price_requests(responses)
        sc = SubscribedCustomer.objects.first()
        assert sc.customer_id == customer.id
        assert sc.stripe_customer_id == "cus_newman"
        assert sc.stripe_subscription_id == "sub_jambalaya_soup"
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED

    def test_dont_sync_inactive_customer(self, responses, customer: Customer) -> None:
        assert SubscribedCustomer.objects.count() == 0
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        customer.deactivate()
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 0
        assert len(responses.calls) == 0
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

    def test_dont_sync_open_source_customer(self, responses) -> None:
        customer = Customer.create(slug="david", name="David Puddy", customer_type=Customer.Type.OPEN_SOURCE)
        assert SubscribedCustomer.objects.count() == 0
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 0
        assert len(responses.calls) == 0
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

    def test_sync_stripe_customer_and_subscription_exists_in_stripe(
        self, responses, httpx_mock, customer: Customer
    ) -> None:
        assert SubscribedCustomer.objects.count() == 0
        add_search_customer_response(responses, stripe_id="newman", customer_id=customer.id)
        add_list_customer_subscriptions_response(responses, stripe_customer_id="newman")
        add_get_admin_users_response(
            httpx_mock,
            customer_id=customer.id,
            admins=(
                ("newman", "newmman@usps.com"),
                ("david", "david@puddy.org"),
            ),
        )
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 4
        assert_customer_search_request(responses.calls[0].request, "test", toolchain_customer_id=customer.id)
        assert_list_customer_subscriptions_request(responses.calls[1].request, stripe_customer_id="newman")
        self._assert_product_and_price_requests(responses)
        sc = SubscribedCustomer.objects.first()
        assert sc.customer_id == customer.id
        assert sc.stripe_customer_id == "newman"
        assert sc.stripe_subscription_id == "sub_jambalaya_soup"
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    DEFAULT_TRIAL_END = datetime.date(2022, 7, 3)

    def _assert_subscription_1(self, customer: Customer, trial_end: datetime.date | None = DEFAULT_TRIAL_END) -> None:
        assert SubscribedCustomer.objects.count() == 1
        sc = SubscribedCustomer.objects.first()
        assert sc.customer_id == customer.id
        assert sc.customer_slug == customer.slug
        assert sc.stripe_customer_id == "newman"
        assert sc.stripe_subscription_id == "sub_1L6dslEfbv3GSgSdlcN25ytd"
        assert sc.plan_name == "Kramer"
        assert sc.plan_price_text == "20$/month"
        assert sc.trial_end == trial_end

    def _assert_subscription_2(self, customer: Customer, with_sub_info: bool = True) -> None:
        assert SubscribedCustomer.objects.count() == 1
        sc = SubscribedCustomer.objects.first()
        assert sc.customer_id == customer.id
        assert sc.customer_slug == customer.slug
        assert sc.stripe_customer_id == "newman"
        assert sc.stripe_subscription_id == "sub_jambalaya_soup"
        if with_sub_info:
            assert sc.plan_name == "Kramer"
            assert sc.plan_price_text == "20$/month"
            assert sc.trial_end == datetime.date(2022, 5, 28)
        else:
            assert sc.plan_name == ""
            assert sc.plan_price_text == ""
            assert sc.trial_end is None

    def test_sync_stripe_customer_exists_no_subscription(self, responses, httpx_mock, customer: Customer) -> None:
        assert SubscribedCustomer.objects.count() == 0
        add_get_admin_users_response(httpx_mock, customer_id=customer.id, admins=(("kramer", "kenny@cosmo.org"),))
        add_search_customer_response(responses, stripe_id="newman", customer_id=customer.id)
        add_list_customer_subscriptions_response(responses, empty=True)
        add_create_customer_subscriptions_response(responses, stripe_customer_id="newman")
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )
        first_billing_month = utcnow().date() + datetime.timedelta(days=5) + relativedelta.relativedelta(months=1)
        billing_anchor_ts = datetime.datetime(
            year=first_billing_month.year, month=first_billing_month.month, day=1, tzinfo=datetime.timezone.utc
        ).timestamp()
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 5
        assert_customer_search_request(responses.calls[0].request, "test", toolchain_customer_id=customer.id)
        assert_list_customer_subscriptions_request(responses.calls[1].request, stripe_customer_id="newman")
        assert_create_customer_subscriptions_request(
            responses.calls[2].request,
            stripe_customer_id="newman",
            toolchain_customer_id=customer.id,
            price_id="festivus",
            trial_period_days=5,
            billing_anchor_ts=int(billing_anchor_ts),
        )
        self._assert_product_and_price_requests(responses)
        self._assert_subscription_2(customer)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    def test_sync_stripe_customer_and_subscription_exists_locally_no_billing_emails(
        self, responses, httpx_mock, customer: Customer
    ) -> None:
        add_get_subscription_response(
            responses, subscription_id="sub_jambalaya_soup", exists=True, stripe_customer_id="newman"
        )
        add_get_admin_users_response(httpx_mock, customer_id=customer.id)  # No admins
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )
        create_subscribed_customer(customer)
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 3
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        self._assert_product_and_price_requests(responses)
        self._assert_subscription_1(customer)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    def test_sync_existing_no_billing_email(self, responses, httpx_mock, customer: Customer) -> None:
        add_get_subscription_response(
            responses,
            subscription_id="sub_jambalaya_soup",
            exists=True,
            stripe_customer_id="newman",
            subscription_status="trialing",
        )
        add_modify_customer_response(responses, stripe_id="newman")
        add_search_customer_response(responses, stripe_id="newman", customer_id=customer.id)
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )
        add_get_admin_users_response(
            httpx_mock,
            customer_id=customer.id,
            admins=(
                ("newman", "newman@usps.com"),
                ("david", "david@puddy.org"),
            ),
        )
        create_subscribed_customer(customer)
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 5
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        assert_customer_search_request(responses.calls[3].request, "test", toolchain_customer_id=customer.id)
        assert_modify_customer(responses.calls[-1].request, stripe_id="newman", billing_email="newman@usps.com")
        self._assert_subscription_1(customer)
        self._assert_product_and_price_requests(responses, reqs=(1, 2))
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    def test_sync_existing_billing_email_already_exists(self, responses, httpx_mock, customer: Customer) -> None:
        add_get_subscription_response(
            responses,
            subscription_id="sub_jambalaya_soup",
            exists=True,
            stripe_customer_id="newman",
            subscription_status="trialing",
        )
        add_search_customer_response(
            responses, stripe_id="newman", customer_id=customer.id, billing_email="jerry@festivus.com"
        )
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )
        add_get_admin_users_response(
            httpx_mock,
            customer_id=customer.id,
            admins=(
                ("newman", "newman@usps.com"),
                ("david", "david@puddy.org"),
            ),
        )
        create_subscribed_customer(customer)
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 4
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        assert_customer_search_request(responses.calls[3].request, "test", toolchain_customer_id=customer.id)
        self._assert_product_and_price_requests(responses, reqs=(1, 2))
        self._assert_subscription_1(customer)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    @pytest.mark.parametrize("status", ["active", "incomplete"])
    def test_sync_stripe_customer_and_active_subscription_with_default_payment(
        self, responses, status: str, prospect: Customer
    ) -> None:
        add_get_subscription_response(
            responses,
            subscription_id="sub_jambalaya_soup",
            exists=True,
            subscription_status=status,
            stripe_customer_id="newman",
        )
        sc = create_subscribed_customer(prospect)
        add_search_customer_response(
            responses,
            stripe_id=sc.stripe_customer_id,
            customer_id=prospect.id,
            add_default_payment=True,
        )
        add_product_and_prices_responses(
            responses, product_id="prod_LcgVoYRbtZeS7i", price_id="price_1KvR8PEfbv3GSgSdnaXqkFUF"
        )
        PeriodicallySyncStripeCustomer.get_or_create(prospect.id, customer_slug=prospect.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 4
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        assert_customer_search_request(responses.calls[1].request, "test", toolchain_customer_id=prospect.id)
        self._assert_product_and_price_requests(responses)
        self._assert_subscription_1(prospect, trial_end=None)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=prospect.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    @pytest.mark.parametrize("status", ["canceled", "past_due", "unpaid"])
    def test_sync_stripe_customer_and_subscription_limited(self, responses, status: str, customer: Customer) -> None:
        add_get_subscription_response(
            responses,
            subscription_id="sub_jambalaya_soup",
            exists=True,
            subscription_status=status,
            stripe_customer_id="newman",
        )
        create_subscribed_customer(customer)
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 1
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        self._assert_subscription_2(customer, with_sub_info=False)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.service_level == Customer.ServiceLevel.LIMITED
        assert loaded_customer.is_limited is True

    def test_dont_sync_stripe_customer_and_subscription_customer_id_mismatch(
        self, responses, customer: Customer
    ) -> None:
        add_get_subscription_response(
            responses,
            subscription_id="sub_jambalaya_soup",
            exists=True,
            subscription_status="past_due",
            stripe_customer_id="little_jerry",
        )
        create_subscribed_customer(customer)
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 1
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        self._assert_subscription_2(customer, with_sub_info=False)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.INFEASIBLE
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE
        assert loaded_customer.is_limited is False

    @pytest.mark.parametrize("status", ["canceled", "past_due", "unpaid"])
    def test_sync_stripe_customer_and_subscription_limited_no_stripe_payment(
        self, responses, status: str, customer: Customer
    ) -> None:
        add_get_subscription_response(
            responses,
            subscription_id="sub_jambalaya_soup",
            exists=True,
            subscription_status=status,
            stripe_customer_id="newman",
        )
        create_subscribed_customer(customer, payout_outside_stripe=True)
        PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        assert SubscribedCustomer.objects.count() == 1
        assert len(responses.calls) == 1
        assert_get_subscriptions_request(responses.calls[0].request, "sub_jambalaya_soup")
        self._assert_subscription_2(customer, with_sub_info=False)
        wu = PeriodicallySyncStripeCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE
        assert loaded_customer.is_limited is False


class TestStripeCustomerSyncCreator(BaseWorkerTests):
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="usps", name="Postal Service", customer_type=Customer.Type.PROSPECT)

    def test_no_recent_customers(self, customer: Customer) -> None:
        customer.created_at = datetime.datetime(2022, 6, 10, tzinfo=datetime.timezone.utc)
        customer.save()
        PeriodicallyCreateStripeCustomerSync.create_or_update(period_minutes=122)
        assert self.do_work() == 1
        self._assert_sync_state()
        assert PeriodicallySyncStripeCustomer.objects.count() == 0

    def test_recent_customers(self, customer: Customer) -> None:
        PeriodicallyCreateStripeCustomerSync.create_or_update(period_minutes=122)
        assert self.do_work() == 1
        self._assert_sync_state()
        assert PeriodicallySyncStripeCustomer.objects.count() == 1
        sync = PeriodicallySyncStripeCustomer.objects.first()
        assert sync.customer_id == customer.id

    def test_recent_customers_already_sinced(self, customer: Customer) -> None:
        pssc, created = PeriodicallySyncStripeCustomer.get_or_create(customer.id, customer_slug="bob")
        mark_work_unit_success(pssc)
        assert created is True
        PeriodicallyCreateStripeCustomerSync.create_or_update(period_minutes=122)
        assert self.do_work() == 1
        self._assert_sync_state()
        assert PeriodicallySyncStripeCustomer.objects.count() == 1

    def _assert_sync_state(self):
        assert PeriodicallyCreateStripeCustomerSync.objects.count() == 1
        wu = PeriodicallyCreateStripeCustomerSync.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
