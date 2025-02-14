# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import stripe
from django.conf import settings

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer
from toolchain.payments.stripe_integration.models import SubscribedCustomer
from toolchain.payments.stripe_integration.stripe_client import StripeCustomersClient, StripeSubscription

_logger = logging.getLogger(__name__)


def handle_subscription_status(*, sc: SubscribedCustomer, subscription: StripeSubscription, customer: Customer) -> bool:
    _logger.info(f"handle_subscription_status: {customer} {sc.stripe_subscription_id=} status: {subscription.status=}")
    if sc.stripe_customer_id != subscription.stripe_customer_id:
        raise ToolchainAssertion(
            f"Customer ID mismatch: subscription is associated with {subscription.stripe_customer_id} while {sc}"
        )
    if sc.payout_outside_of_stripe:
        _logger.info(f"Ignore subscription {subscription} for {sc} ({customer}) since it is not paying using stripe.")
        return False
    if subscription.is_limited:
        customer.set_service_level(Customer.ServiceLevel.LIMITED)
    elif subscription.is_trial:
        customer.set_type(Customer.Type.PROSPECT)
        customer.set_service_level(Customer.ServiceLevel.FULL_SERVICE)
    elif subscription.is_active:
        _maybe_activate_customer(sc, customer, subscription)
    else:
        _logger.warning(
            f"subscription_status_not_implemented: {customer} {sc.stripe_subscription_id=} status: {subscription.status=}"
        )
    return True


def _maybe_activate_customer(sc: SubscribedCustomer, customer: Customer, subscription: StripeSubscription):
    if customer.customer_type == Customer.Type.CUSTOMER:
        return
    client = StripeCustomersClient(toolchain_env_name=settings.TOOLCHAIN_ENV.get_env_name())
    stripe_customer = client.get_customer_by_toolchain_id(toolchain_customer_id=customer.id)
    if (
        not stripe_customer
        or stripe_customer.toolchain_id != customer.id
        or stripe_customer.stripe_id != sc.stripe_customer_id
    ):
        raise ToolchainAssertion(f"Unexpected stripe customer: {stripe_customer=} {sc=} {customer=}")
    if not stripe_customer.has_default_payment_method:
        client.cancel_subscription(subscription_id=subscription.stripe_id)
        return
    customer.set_type(Customer.Type.CUSTOMER)
    customer.set_service_level(Customer.ServiceLevel.FULL_SERVICE)


def _handle_subscription_update(event: stripe.Event):
    subscription = StripeSubscription.from_record(event.data.object)
    sc = SubscribedCustomer.get_or_none(
        stripe_subscription_id=subscription.stripe_id, stripe_customer_id=subscription.stripe_customer_id
    )
    if not sc:
        # This can happen for non sass customer we have in stripe and it is totally fine.
        _logger.info(
            f"no SubscribedCustomer (non sass customer) for subscription={subscription.stripe_id}, stripe_customer={subscription.stripe_customer_id}."
        )
        return
    customer = Customer.get_for_id_or_none(customer_id=sc.customer_id)
    if not customer:
        _logger.warning(f"Unknown/inactive Customer for {sc}")
        return
    handled = handle_subscription_status(sc=sc, customer=customer, subscription=subscription)
    if handled:
        sc.force_updated()


_HANDLERS = {
    "customer.subscription.updated": _handle_subscription_update,
    "customer.subscription.deleted": _handle_subscription_update,
}


def handle_event(event: stripe.Event) -> bool:
    handler_func = _HANDLERS.get(event.type)
    if not handler_func:
        return False
    handler_func(event)
    return True
