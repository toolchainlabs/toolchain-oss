# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from enum import Enum, unique

from django.db.models import BooleanField, CharField, DateField, DateTimeField, IntegerField

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.helpers import create_or_update_singleton
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.util.helpers import get_choices
from toolchain.workflow.models import WorkUnitPayload

_logger = logging.getLogger(__name__)

transaction = TransactionBroker("stripe_integration")


@unique
class CustomerSubscriptionState(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SubscribedCustomer(ToolchainModel):
    customer_id = CharField(max_length=22, primary_key=True, unique=True, db_index=True, editable=False)
    stripe_customer_id = CharField(max_length=48, unique=True, db_index=True, editable=False)
    created = DateTimeField(editable=False, default=utcnow)
    modified = DateTimeField(auto_now=True)
    stripe_subscription_id = CharField(max_length=48, default="")
    # For Admin UI (toolshed) and __str__ display purposes only
    customer_slug = CharField(max_length=64)
    plan_name = CharField(max_length=48, null=True)  # noqa: DJ01
    plan_price_text = CharField(max_length=48, null=True)  # noqa: DJ01
    trial_end = DateField(null=True)
    payout_outside_of_stripe = BooleanField(default=False)

    # _state is used by django internally.
    _subs_state = CharField(
        max_length=10,
        default=CustomerSubscriptionState.ACTIVE.value,
        db_column="state",
        choices=get_choices(CustomerSubscriptionState),
    )

    @classmethod
    def get_or_create(cls, customer_id: str, customer_slug: str, stripe_customer_id: str) -> SubscribedCustomer:
        obj, created = cls.objects.get_or_create(
            customer_id=customer_id, customer_slug=customer_slug, stripe_customer_id=stripe_customer_id
        )
        if created:
            _logger.info(f"created SubscribedCustomer {obj}")
        return obj

    @classmethod
    def get_by_customer_id(cls, customer_id: str) -> SubscribedCustomer | None:
        return cls.get_or_none(customer_id=customer_id)  # TODO: active only?

    def set_subscription_info(
        self, subscription_id: str, trial_end: datetime.date | None, plan: str, plan_price_text: str
    ) -> None:
        if not subscription_id:
            raise ToolchainAssertion("Invalid subscription_id")
        if (
            self.stripe_subscription_id == subscription_id
            and self.trial_end == trial_end
            and self.plan_name == plan
            and self.plan_price_text == plan_price_text
        ):
            return
        _logger.info(
            f"set_stripe_subscription_id current={self.stripe_subscription_id or '<EMPTY>'} new={subscription_id} {plan} ({plan_price_text}) {self}"
        )
        self.stripe_subscription_id = subscription_id
        self.plan_price_text = plan_price_text
        self.plan_name = plan
        self.trial_end = trial_end
        self.save()

    def force_updated(self) -> None:
        """force updating modified time field."""
        _logger.info(f"{self} updated")
        self.save()

    def __str__(self) -> str:
        return f"subscribed customer: {self.customer_slug}{self.customer_id} stripe_id={self.stripe_customer_id}"


class PeriodicallySyncStripeCustomer(WorkUnitPayload):
    customer_id = CharField(max_length=22, editable=False)  # Toolchain(django/site/models.py:Customer id)
    force_run = BooleanField(default=False)
    # For Admin UI (toolshed) and __str__ display purposes only
    customer_slug = CharField(max_length=64, null=True)  # noqa: DJ01

    @classmethod
    def get_or_create(cls, customer_id: str, customer_slug: str) -> tuple[PeriodicallySyncStripeCustomer, bool]:
        pssc, created = cls.objects.get_or_create(customer_id=customer_id, defaults={"customer_slug": customer_slug})
        if created:
            _logger.info(f"Created {pssc}")
        else:
            pssc.maybe_update_slug(customer_slug)
        return pssc, created

    def maybe_update_slug(self, customer_slug: str) -> None:
        # temporary method to backfill slug for existing objects.
        if self.customer_slug == customer_slug:
            return
        self.customer_slug = customer_slug
        self.save()

    def __str__(self) -> str:
        return f"PeriodicallySyncStripeCustomer {self.customer_slug} customer_id={self.customer_id}"

    @property
    def description(self) -> str:
        return str(self)


class PeriodicallyCreateStripeCustomerSync(WorkUnitPayload):
    period_minutes = IntegerField()

    @classmethod
    def create_or_update(cls, period_minutes: int | None) -> PeriodicallyCreateStripeCustomerSync:
        return create_or_update_singleton(cls, transaction, period_minutes=period_minutes)
