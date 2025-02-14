# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

import stripe
from stripe.api_resources import Customer as StripeCustomerRecord
from stripe.api_resources import Subscription

from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


@dataclass
class StripeSubscription:
    # Subscription statuses https://stripe.com/docs/api/subscriptions/object#subscription_object-status
    # TODO: decide what to do w/ incomplete_expired, probably goes into LIMITED
    _LIMITED = frozenset(("past_due", "canceled", "unpaid"))
    _ACTIVE = frozenset(("active", "incomplete"))
    stripe_id: str
    stripe_customer_id: str
    status: str
    price_id: str
    product_id: str
    start_date: datetime.date
    trial_end: datetime.date | None

    @classmethod
    def from_record(cls, record: Subscription) -> StripeSubscription:
        # https://stripe.com/docs/api/subscriptions/object?lang=python
        return cls(
            stripe_id=record.id,
            stripe_customer_id=record.customer,
            status=record.status,
            product_id=record.plan.product,
            price_id=record.plan.id,
            start_date=datetime.datetime.fromtimestamp(record.start_date, tz=datetime.timezone.utc).date(),
            trial_end=datetime.datetime.fromtimestamp(record.trial_end, tz=datetime.timezone.utc).date()
            if record.trial_end
            else None,
        )

    @property
    def is_limited(self) -> bool:
        return self.status in self._LIMITED

    @property
    def is_trial(self) -> bool:
        # https://stripe.com/docs/api/subscriptions/object#subscription_object-status
        return self.status == "trialing"

    @property
    def is_active(self) -> bool:
        return self.status in self._ACTIVE


@dataclass
class StripeCustomer:
    toolchain_id: str
    stripe_id: str
    name: str
    billing_email: str | None
    has_default_payment_method: bool


@dataclass
class StripeProductPrice:
    product_id: str
    price_id: str
    price_nick_name: str
    product_name: str
    product_description: str
    monthly_usd_cost: int


_TOOLCHAIN_DEFAULT_PLAN_FIELD = "TOOLCHAIN_DEFAULT_PLAN"


class StripeCustomersClient:
    _TOOLCHAIN_ID_FIELD = "toolchain_id"
    _TOOLCHAIN_ENV_FIELD = "toolchain_env"

    def __init__(self, toolchain_env_name: str) -> None:
        """The `toolchain_env_name` is mostly for dev env, it will have the toolchain engineers's name/namespace and
        will ensure multiple engineers can develop against the stripe API without stepping on each other's data."""
        if not toolchain_env_name:
            raise ToolchainAssertion("toolchain_env_name can't be empty.")
        self._tc_env = toolchain_env_name

    def _get_metadata(self, toolchain_customer_id: str) -> dict[str, str]:
        return {
            self._TOOLCHAIN_ID_FIELD: toolchain_customer_id,
            self._TOOLCHAIN_ENV_FIELD: self._tc_env,
        }

    def _get_toolchain_metadata_query(self, toolchain_customer_id: str) -> str:
        return f'metadata["{self._TOOLCHAIN_ID_FIELD}"]:"{toolchain_customer_id}" AND metadata["{self._TOOLCHAIN_ENV_FIELD}"]:"{self._tc_env}"'

    def get_customer_by_toolchain_id(self, toolchain_customer_id: str) -> StripeCustomer | None:
        # https://stripe.com/docs/search#metadata
        results = stripe.Customer.search(query=self._get_toolchain_metadata_query(toolchain_customer_id))
        if len(results) > 1:
            raise ToolchainAssertion(
                f"More than one stripe customer object with toolchain id: {toolchain_customer_id} - {len(results)}"
            )
        return None if results.is_empty else self._to_stripe_customer(results.data[0])

    def get_or_create_customer(
        self, *, name: str, toolchain_customer_id: str, billing_email: str | None
    ) -> tuple[StripeCustomer, bool]:
        customer = self.get_customer_by_toolchain_id(toolchain_customer_id)
        if customer:
            return customer, False
        return (
            self._create_customer(name=name, toolchain_customer_id=toolchain_customer_id, billing_email=billing_email),
            True,
        )

    def update_customer_billing_email(self, *, stripe_customer_id: str, billing_email: str) -> None:
        # https://stripe.com/docs/api/customers/update?lang=python
        stripe.Customer.modify(stripe_customer_id, email=billing_email)

    def _create_customer(self, *, name: str, toolchain_customer_id: str, billing_email: str | None) -> StripeCustomer:
        # https://stripe.com/docs/api/customers/create?lang=python
        if not name or not toolchain_customer_id:
            # It is really bad if those are empty/null so we make this check here to prevent any data corruption issues.
            raise ToolchainAssertion("Invalid args for customer creation.")
        _logger.info(f"create_stripe_customer {name=} {toolchain_customer_id=}")
        md = self._get_metadata(toolchain_customer_id)
        customer_record = stripe.Customer.create(name=name, metadata=md, email=billing_email)
        return self._to_stripe_customer(customer_record)

    def _to_stripe_customer(self, record: StripeCustomerRecord) -> StripeCustomer:
        # https://stripe.com/docs/api/customers/object
        return StripeCustomer(
            stripe_id=record.id,
            name=record.name,
            toolchain_id=record.metadata[self._TOOLCHAIN_ID_FIELD],
            billing_email=record.email,
            # https://stripe.com/docs/api/customers/object#customer_object-invoice_settings
            has_default_payment_method=bool(record.invoice_settings.default_payment_method),
        )

    def create_customer_portal_session(self, stripe_customer_id: str, return_url: str) -> str:
        # https://stripe.com/docs/api/customer_portal/sessions/create
        session = stripe.billing_portal.Session.create(customer=stripe_customer_id, return_url=return_url)
        return session.url

    def get_customer_subscriptions(self, stripe_customer_id: str) -> tuple[StripeSubscription, ...]:
        # https://stripe.com/docs/api/subscriptions/list?lang=python
        resp = stripe.Subscription.list(customer=stripe_customer_id)
        return tuple(StripeSubscription.from_record(sb) for sb in resp.data)

    def create_trial_subscription(
        self,
        *,
        toolchain_customer_id: str,
        stripe_customer_id: str,
        price_id: str,
        trial_period_days: int,
        billing_anchor: datetime.date,
    ) -> StripeSubscription:
        # https://stripe.com/docs/api/subscriptions/create?lang=python
        md = self._get_metadata(toolchain_customer_id)
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{"price": price_id}],
            metadata=md,
            trial_period_days=trial_period_days,
            billing_cycle_anchor=datetime.datetime(
                year=billing_anchor.year,
                month=billing_anchor.month,
                day=billing_anchor.day,
                tzinfo=datetime.timezone.utc,
            ),
        )
        return StripeSubscription.from_record(subscription)

    def get_subscription(self, subscription_id: str) -> StripeSubscription:
        # https://stripe.com/docs/api/subscriptions/retrieve?lang=python
        resp = stripe.Subscription.retrieve(id=subscription_id)
        return StripeSubscription.from_record(resp)

    def cancel_subscription(self, subscription_id: str) -> None:
        stripe.Subscription.delete(subscription_id)


def get_product_and_price_info(*, product_id: str, price_id: str) -> StripeProductPrice:
    # https://stripe.com/docs/api/products/retrieve?lang=python
    product = stripe.Product.retrieve(product_id)
    # https://stripe.com/docs/api/prices/retrieve
    price = stripe.Price.retrieve(price_id)
    if price.product != product.id:
        raise ToolchainAssertion(
            f"Price {price.id} - {price.nickname} is not under product {product.id} - {product.name}"
        )

    return StripeProductPrice(
        product_id=product.id,
        price_id=price.id,
        price_nick_name=price.nickname,
        product_name=product.name,
        product_description=product.description,
        monthly_usd_cost=_get_monthly_cost(price),
    )


def get_default_stripe_product() -> StripeProductPrice:
    # https://stripe.com/docs/api/products/search
    products = stripe.Product.search(query=f'active:"true" AND metadata["{_TOOLCHAIN_DEFAULT_PLAN_FIELD}"]:"True"')
    if len(products) != 1:
        raise ToolchainAssertion("Unable to determine default Toolchain Stripe product")
    product = products.data[0]
    # https://stripe.com/docs/api/prices/search
    prices_responses = stripe.Price.search(query=f'active:"true" AND product:"{product.id}"')
    if prices_responses.is_empty:
        raise ToolchainAssertion(f"no prices for default product: {product.name} id={product.id}")
    price = sorted(prices_responses.data, key=lambda price: price.unit_amount)[0]
    return StripeProductPrice(
        product_id=product.id,
        price_id=price.id,
        price_nick_name=price.nickname,
        product_name=product.name,
        product_description=product.description,
        monthly_usd_cost=_get_monthly_cost(price),
    )


def _get_monthly_cost(price: stripe.Price) -> int:
    # Making some sanity checks here since we make assumptions about this price in other parts of the app.
    if price.recurring.interval != "month":
        raise ToolchainAssertion(f"Unexpected price internval: {price.recurring.interval}")
    if price.recurring.interval_count != 1:
        raise ToolchainAssertion(f"Unexpected price internval count: {price.recurring.interval_count}")
    # https://stripe.com/docs/api/prices/object#price_object-unit_amount
    return int(price.unit_amount / 100)  # unit ammount is in cents.
