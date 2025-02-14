# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest
from stripe import Event

from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import Customer
from toolchain.payments.stripe_integration.handlers import handle_event
from toolchain.payments.stripe_integration.models import SubscribedCustomer
from toolchain.payments.stripe_integration.test_utils.model_utils import create_subscribed_customer
from toolchain.payments.stripe_integration.test_utils.utils import (
    add_cancel_subscription_response,
    add_search_customer_response,
    assert_cancel_subscriptions_request,
    assert_customer_search_request,
    load_fixture,
)
from toolchain.util.test.util import assert_messages


def load_event(fixture_name: str, object_modifier: dict | None = None) -> Event:
    fixture = load_fixture(fixture_name)
    if object_modifier:
        fixture["data"]["object"].update(object_modifier)
    return Event.construct_from(fixture, key="festivus")


def load_event_for_sc(fixture_name: str, sc: SubscribedCustomer, status: str | None = None) -> Event:
    modifier = {"id": sc.stripe_subscription_id, "customer": sc.stripe_customer_id}
    if status:
        modifier["status"] = status
    return load_event(fixture_name, modifier)


def test_unhandled_event() -> None:
    event_fixture = load_event("customer_updated_webhook")
    assert handle_event(event_fixture) is False


@pytest.mark.django_db()
class TestStripeSubscriptionUpdate:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc", customer_type=Customer.Type.PROSPECT)

    @pytest.fixture()
    def subscribed_customer(self, customer: Customer) -> SubscribedCustomer:
        return create_subscribed_customer(customer)

    def _assert_sc_updated(self, sc) -> None:
        loaded_sc = SubscribedCustomer.objects.get(stripe_customer_id=sc.stripe_customer_id)
        assert loaded_sc.modified.timestamp() == pytest.approx(utcnow().timestamp())

    def test_subscription_updated_no_sc(self, caplog) -> None:
        event_fixture = load_event("subscription_updated_webhook")
        assert handle_event(event_fixture) is True
        assert_messages(caplog, r"no SubscribedCustomer \(non sass customer\) for subscription")

    def test_subscription_updated_no_inactive_customer(
        self, caplog, customer: Customer, subscribed_customer: SubscribedCustomer
    ) -> None:
        customer.deactivate()
        event_fixture = load_event_for_sc("subscription_updated_webhook", subscribed_customer)
        assert handle_event(event_fixture) is True
        assert_messages(caplog, "Unknown/inactive Customer for")

    def test_subscription_updated_to_active_with_default_payment(
        self, responses, customer: Customer, subscribed_customer: SubscribedCustomer
    ) -> None:
        assert customer.customer_type == Customer.Type.PROSPECT  # sanity check
        customer.set_service_level(Customer.ServiceLevel.LIMITED)
        event_fixture = load_event_for_sc("subscription_updated_webhook", subscribed_customer)
        add_search_customer_response(
            responses,
            stripe_id=subscribed_customer.stripe_customer_id,
            customer_id=customer.id,
            add_default_payment=True,
        )
        assert handle_event(event_fixture) is True
        self._assert_sc_updated(subscribed_customer)
        assert len(responses.calls) == 1
        assert_customer_search_request(responses.calls[0].request, "test", toolchain_customer_id=customer.id)
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.is_limited is False
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    def test_subscription_updated_to_active_without_default_payment(
        self, responses, customer: Customer, subscribed_customer: SubscribedCustomer
    ) -> None:
        assert customer.customer_type == Customer.Type.PROSPECT  # sanity check
        event_fixture = load_event_for_sc("subscription_updated_webhook", subscribed_customer)
        add_search_customer_response(
            responses,
            stripe_id=subscribed_customer.stripe_customer_id,
            customer_id=customer.id,
            add_default_payment=False,
        )
        add_cancel_subscription_response(responses, subscription_id=subscribed_customer.stripe_subscription_id)
        assert handle_event(event_fixture) is True
        self._assert_sc_updated(subscribed_customer)
        assert len(responses.calls) == 2
        assert_customer_search_request(responses.calls[0].request, "test", toolchain_customer_id=customer.id)
        assert_cancel_subscriptions_request(
            responses.calls[1].request, subscription_id=subscribed_customer.stripe_subscription_id
        )
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.is_limited is False
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    def test_subscription_updated_to_active_for_customer(
        self, customer: Customer, subscribed_customer: SubscribedCustomer
    ) -> None:
        customer.set_type(Customer.Type.CUSTOMER)
        event_fixture = load_event_for_sc("subscription_updated_webhook", subscribed_customer)
        assert handle_event(event_fixture) is True
        self._assert_sc_updated(subscribed_customer)
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.is_limited is False
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE

    def test_subscription_updated_limited(self, customer: Customer, subscribed_customer: SubscribedCustomer) -> None:
        assert customer.customer_type == Customer.Type.PROSPECT  # sanity check
        assert customer.service_level == Customer.ServiceLevel.FULL_SERVICE  # sanity check
        event_fixture = load_event_for_sc("subscription_updated_webhook", subscribed_customer, status="past_due")
        assert handle_event(event_fixture) is True
        self._assert_sc_updated(subscribed_customer)
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.is_limited is True
        assert loaded_customer.service_level == Customer.ServiceLevel.LIMITED

    def test_subscription_deleted(self, customer: Customer, subscribed_customer: SubscribedCustomer) -> None:
        assert customer.service_level == Customer.ServiceLevel.FULL_SERVICE  # sanity check
        event_fixture = load_event_for_sc("customer_subscription_deleted_webhook", subscribed_customer)
        assert handle_event(event_fixture) is True
        self._assert_sc_updated(subscribed_customer)
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.PROSPECT
        assert loaded_customer.is_limited is True
        assert loaded_customer.service_level == Customer.ServiceLevel.LIMITED

    @pytest.mark.parametrize("fixture", ["customer_subscription_deleted_webhook", "subscription_updated_webhook"])
    def test_subscription_change_payments_outside_stripe(self, fixture: str) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc", customer_type=Customer.Type.CUSTOMER)
        sc = create_subscribed_customer(customer, payout_outside_stripe=True)
        assert customer.service_level == Customer.ServiceLevel.FULL_SERVICE  # sanity check
        assert customer.customer_type == Customer.Type.CUSTOMER  # sanity check
        event_fixture = load_event_for_sc(fixture, sc)
        assert handle_event(event_fixture) is True
        loaded_sc = SubscribedCustomer.objects.get(stripe_customer_id=sc.stripe_customer_id)
        assert loaded_sc.modified == loaded_sc.created  # not updated.
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.customer_type == Customer.Type.CUSTOMER
        assert loaded_customer.is_limited is False
        assert loaded_customer.service_level == Customer.ServiceLevel.FULL_SERVICE
