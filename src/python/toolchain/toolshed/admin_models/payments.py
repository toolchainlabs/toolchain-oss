# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from django.conf import settings
from django.contrib.admin import ModelAdmin, display
from humanize.filesize import naturalsize

from toolchain.payments.amberflo_integration.models import (
    AmberfloCustomerMTDMetrics,
    PeriodicallyCreateAmberfloCustomerSync,
    PeriodicallySyncAmberfloCustomer,
)
from toolchain.payments.stripe_integration.models import (
    PeriodicallyCreateStripeCustomerSync,
    PeriodicallySyncStripeCustomer,
    SubscribedCustomer,
)
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin, get_link


class SubscribedCustomerModelAdmin(ModelAdmin):
    _BASE_URL = "https://dashboard.stripe.com/test" if settings.TOOLCHAIN_ENV.is_dev else "https://dashboard.stripe.com"
    list_display = (
        "customer",
        "stripe_customer_link",
        "stripe_subscription_link",
        "created",
        "modified",
        "payout_outside_of_stripe",
    )
    fields = (
        ("customer_slug", "customer_id", "stripe_customer_link", "stripe_subscription_link"),
        (
            "stripe_subscription_id",
            "payout_outside_of_stripe",
        ),
        ("plan_name", "plan_price_text", "trial_end"),
        ("created", "modified"),
    )
    readonly_fields = (
        "customer_id",
        "created",
        "modified",
        "stripe_customer_link",
        "stripe_subscription_link",
        "plan_name",
        "plan_price_text",
        "trial_end",
    )

    def customer(self, sc: SubscribedCustomer) -> str:
        return f"{sc.customer_slug}/{sc.customer_id}"

    @display(description="Stripe Customer")
    def stripe_customer_link(self, sc: SubscribedCustomer) -> str:
        url_path = f"{self._BASE_URL}/customers/{sc.stripe_customer_id}"
        return get_link(url_path, sc.stripe_customer_id)

    @display(description="Stripe Subscription")
    def stripe_subscription_link(self, sc: SubscribedCustomer) -> str:
        if not sc.stripe_subscription_id:
            return "N/A"
        url_path = f"{self._BASE_URL}/subscriptions/{sc.stripe_subscription_id}"
        return get_link(url_path, sc.stripe_subscription_id)

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class AmberfloCustomerMTDMetricsModelAdmin(ReadOnlyModelAdmin):
    _BASE_URL = "https://ui.amberflo.io/usage-explorer/by-customer"
    list_display = ("customer", "month", "cache_read", "cache_write", "amberflo_dashboard", "last_updated")
    fields = (
        ("customer_slug", "customer_id", "last_updated"),
        ("month", "cache_read", "cache_read_bytes", "cache_write", "cache_write_bytes"),
        ("amberflo_dashboard",),
    )

    def customer(self, metrics: AmberfloCustomerMTDMetrics) -> str:
        return f"{metrics.customer_slug}/{metrics.customer_id}"

    def amberflo_dashboard(self, metrics: AmberfloCustomerMTDMetrics) -> str:
        url_path = f"{self._BASE_URL}/prod_v1_{metrics.customer_id}"
        return get_link(url_path, metrics.customer_slug)

    def month(self, metrics: AmberfloCustomerMTDMetrics) -> str:
        return f"{metrics.metric_month}/{metrics.metric_year}"

    def cache_read(self, metrics: AmberfloCustomerMTDMetrics) -> str:
        return naturalsize(metrics.cache_read_bytes)

    def cache_write(self, metrics: AmberfloCustomerMTDMetrics) -> str:
        return naturalsize(metrics.cache_write_bytes)

    def last_updated(self, metrics: AmberfloCustomerMTDMetrics) -> datetime.datetime:
        return metrics.modified_at


def get_payments_models():
    return {
        SubscribedCustomer: SubscribedCustomerModelAdmin,
        PeriodicallySyncStripeCustomer: ReadOnlyModelAdmin,
        PeriodicallySyncAmberfloCustomer: ReadOnlyModelAdmin,
        PeriodicallyCreateStripeCustomerSync: ReadOnlyModelAdmin,
        PeriodicallyCreateAmberfloCustomerSync: ReadOnlyModelAdmin,
        AmberfloCustomerMTDMetrics: AmberfloCustomerMTDMetricsModelAdmin,
    }
