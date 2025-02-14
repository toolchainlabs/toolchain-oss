# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from dateutil import relativedelta
from django.conf import settings

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer
from toolchain.payments.stripe_integration.handlers import handle_subscription_status
from toolchain.payments.stripe_integration.models import (
    PeriodicallyCreateStripeCustomerSync,
    PeriodicallySyncStripeCustomer,
    SubscribedCustomer,
)
from toolchain.payments.stripe_integration.stripe_client import (
    StripeCustomersClient,
    StripeSubscription,
    get_product_and_price_info,
)
from toolchain.users.client.user_client import UserClient
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PeriodicStripeCustomerSyncer(Worker):
    work_unit_payload_cls = PeriodicallySyncStripeCustomer
    _DEFAULT_SYNC_PERIOD = datetime.timedelta(hours=2)
    _TIME_BETWEEN_UPDATES = datetime.timedelta(
        days=1
    )  # Will not call the stripe API to update subscription if there was an update in the last day.
    _BILLABLE_CUSTOMER_TYPES = frozenset((Customer.Type.PROSPECT, Customer.Type.CUSTOMER))
    # We want stuff to blow up and not load/start if those are not properly configured.
    _PRICE_ID = settings.STRIPE_CONFIG.trial_price_id
    _FREE_TRIAL_DAYS = settings.STRIPE_CONFIG.trial_period_days
    work_unit_payload_cls = PeriodicallySyncStripeCustomer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = StripeCustomersClient(toolchain_env_name=settings.TOOLCHAIN_ENV.get_env_name())

    def do_work(self, work_unit_payload: PeriodicallySyncStripeCustomer) -> bool:
        customer = Customer.get_for_id_or_none(work_unit_payload.customer_id)
        if not customer:
            _logger.warning(f"customer {work_unit_payload.customer_id} not active/exists.")
            # Inactive customer, so no need to run sync for this anymore.
            # TODO: Might want to make sure/disable the customer in Stripe too.
            return True
        if customer.customer_type not in self._BILLABLE_CUSTOMER_TYPES:
            _logger.info(f"customer {customer} type={customer.customer_type.value} not supported for billing.")
            return True
        sc = SubscribedCustomer.get_by_customer_id(work_unit_payload.customer_id)
        new_customer_flow = False
        if not sc:
            new_customer_flow = True
            billing_email = self._get_default_billing_email(customer)
            sc = self._create_stripe_customer(customer, billing_email=billing_email)
        if not sc.stripe_subscription_id:
            new_customer_flow = True
            subscription = self._create_stripe_subscription(sc)
            if not subscription:
                # Multiple or no subscription, we don't know what to do in this state.
                # which is fine, can be a transient state due to edits via the stripe dashboard.
                return False
            self._set_subscription_info(sc, subscription)
            handle_subscription_status(subscription=subscription, customer=customer, sc=sc)
            return False
        if new_customer_flow:
            return False
        # In most cases, this is the used flow (update existing subscription) so we want to avoid making API calls to stripe if we had a recent update since
        # this flow is here just to cover for cases we missed or were not able to properly handle web hooks from stripe.
        next_update_time = sc.modified + self._TIME_BETWEEN_UPDATES
        if next_update_time < utcnow() or work_unit_payload.force_run:
            self._handle_existing_subscription(sc=sc, customer=customer)
            sc.force_updated()  # mark as updated even if we didn't do anything so the next run will be a no-op until _TIME_BETWEEN_UPDATES elspses
        return False

    def _maybe_update_billing_email(self, customer: Customer):
        billing_email = self._get_default_billing_email(customer)
        if not billing_email:
            return
        stripe_customer = self._client.get_customer_by_toolchain_id(toolchain_customer_id=customer.id)
        if not stripe_customer:
            raise ToolchainAssertion(f"Can't find stripe customer for {customer}")
        if stripe_customer.billing_email:
            return
        _logger.info(f"Update billing email for {customer} ({stripe_customer.stripe_id}) to {billing_email}")
        self._client.update_customer_billing_email(
            stripe_customer_id=stripe_customer.stripe_id, billing_email=billing_email
        )

    def _set_subscription_info(self, sc: SubscribedCustomer, subscription: StripeSubscription) -> None:
        trial_end = subscription.trial_end if subscription.is_trial else None
        prod_price_info = get_product_and_price_info(product_id=subscription.product_id, price_id=subscription.price_id)
        price_txt = f"{prod_price_info.monthly_usd_cost}$/month"
        sc.set_subscription_info(
            subscription.stripe_id, trial_end=trial_end, plan=prod_price_info.product_name, plan_price_text=price_txt
        )

    def _get_default_billing_email(self, customer: Customer) -> str | None:
        uc = UserClient.for_customer(django_settings=settings, customer_id=customer.id)
        admin_users = uc.get_admin_users()
        if not admin_users:
            _logger.info(f"no admins for: {customer}")
            return None
        admin = admin_users[0]
        _logger.info(f"using admin: {admin.username}/{admin.email} out of {len(admin_users)} admins for {customer}")
        return admin.email

    def _handle_existing_subscription(self, sc: SubscribedCustomer, customer: Customer) -> StripeSubscription:
        _logger.info(f"{sc} has subscription id")
        sub = self._client.get_subscription(sc.stripe_subscription_id)
        handle_subscription_status(subscription=sub, customer=customer, sc=sc)
        if sub.is_trial or sub.is_active:
            self._set_subscription_info(sc, sub)
        if sub.is_trial:
            self._maybe_update_billing_email(customer)
        return sub

    def _create_stripe_customer(self, customer: Customer, billing_email: str | None) -> SubscribedCustomer:
        stripe_record, _ = self._client.get_or_create_customer(
            name=customer.name, toolchain_customer_id=customer.id, billing_email=billing_email
        )
        if stripe_record.toolchain_id != customer.id:
            raise ToolchainAssertion(f"Mismatch in toolchain customer id for {customer=} {stripe_record=}")
        return SubscribedCustomer.get_or_create(
            customer_id=customer.id, customer_slug=customer.slug, stripe_customer_id=stripe_record.stripe_id
        )

    def _create_stripe_subscription(self, sc: SubscribedCustomer) -> StripeSubscription | None:
        existing_subs = self._client.get_customer_subscriptions(stripe_customer_id=sc.stripe_customer_id)
        if existing_subs:
            if len(existing_subs) == 1:
                return existing_subs[0]
            _logger.warning(f"More than one subscription for customer: {sc} - this is not supported/implemented")
            return None
        first_billing_month = (
            utcnow().date() + datetime.timedelta(days=self._FREE_TRIAL_DAYS) + relativedelta.relativedelta(months=1)
        )
        billing_anchor = datetime.date(year=first_billing_month.year, month=first_billing_month.month, day=1)
        _logger.info(f"create trial subscription: {sc} trial_period_days={self._FREE_TRIAL_DAYS} {billing_anchor=}")
        subscription = self._client.create_trial_subscription(
            toolchain_customer_id=sc.customer_id,
            stripe_customer_id=sc.stripe_customer_id,
            price_id=self._PRICE_ID,
            trial_period_days=self._FREE_TRIAL_DAYS,
            billing_anchor=billing_anchor,
        )
        return subscription

    def on_reschedule(self, work_unit_payload: PeriodicallySyncStripeCustomer) -> datetime.datetime:
        if work_unit_payload.force_run:
            work_unit_payload.force_run = False
            work_unit_payload.save()
        return utcnow() + self._DEFAULT_SYNC_PERIOD


class StripeCustomerSyncCreator(Worker):
    work_unit_payload_cls = PeriodicallyCreateStripeCustomerSync

    def do_work(self, work_unit_payload: PeriodicallyCreateStripeCustomerSync) -> bool:
        since = utcnow() - datetime.timedelta(hours=24)
        # Not expecting this to reutrn a ton of data (since we only query for customers created in the last day)
        customers_qs = Customer.active_qs().filter(created_at__gte=since)
        customer_id_map = {customer.id: customer for customer in customers_qs}
        if not customer_id_map:
            return False
        existing_sync_qs = PeriodicallySyncStripeCustomer.objects.filter(customer_id__in=customer_id_map.keys())
        if existing_sync_qs.count() == len(customer_id_map):
            # all the new customer IDs are already accounted for in PeriodicallySyncStripeCustomer.
            return False
        # This logic prefers to make multiple DB roundtrip rather than try to load the PeriodicallySyncStripeCustomer into memory.
        # Since the customer_ids should be small, the number of roundtrips should also be small.
        new_sync_objects_count = 0
        for customer_id, customer in customer_id_map.items():
            _, created = PeriodicallySyncStripeCustomer.get_or_create(customer_id, customer_slug=customer.slug)
            if created:
                new_sync_objects_count += 1
        _logger.info(f"created {new_sync_objects_count} new sync objects for {len(customer_id_map)}")
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyCreateStripeCustomerSync) -> datetime.datetime:
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)
