# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from django.conf import settings

from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import Customer
from toolchain.payments.amberflo_integration.amberflo_client import AmberfloCustomersClient, AmberfloTransientError
from toolchain.payments.amberflo_integration.models import (
    AmberfloCustomerMTDMetrics,
    PeriodicallyCreateAmberfloCustomerSync,
    PeriodicallySyncAmberfloCustomer,
)
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PeriodicAmberCustomerSyncer(Worker):
    work_unit_payload_cls = PeriodicallySyncAmberfloCustomer
    _DEFAULT_SYNC_PERIOD = datetime.timedelta(hours=12)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = AmberfloCustomersClient.from_settings(settings)

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        return WorkExceptionCategory.TRANSIENT if isinstance(exception, AmberfloTransientError) else None

    def transient_error_retry_delay(
        self, work_unit_payload: PeriodicallySyncAmberfloCustomer, exception: Exception
    ) -> datetime.timedelta | None:
        return datetime.timedelta(hours=1)

    def do_work(self, work_unit_payload: PeriodicallySyncAmberfloCustomer) -> bool:
        customer = Customer.get_for_id_or_none(work_unit_payload.customer_id)
        if not customer:
            _logger.warning(f"customer {work_unit_payload.customer_id} not active/exists.")
            # Inactive customer, so no need to run sync for this anymore.
            # TODO: Might want to make sure/disable the customer in Stripe too.
            return True
        self._maybe_create_amberflo_customer(customer)
        self._update_metrics(customer)
        return False

    def _maybe_create_amberflo_customer(self, customer: Customer) -> None:
        amberflo_customer = self._client.get_customer(toolchain_customer_id=customer.id)
        if amberflo_customer:
            return
        self._client.create_customer(toolchain_customer_id=customer.id, name=customer.name)

    def _update_metrics(self, customer: Customer) -> None:
        today = utcnow().date()
        if today.day < 2:
            previous_month = today - datetime.timedelta(days=4)
            from_day = datetime.date(year=previous_month.year, month=previous_month.month, day=1)
            to_day = datetime.date(year=today.year, month=today.month, day=1)
            update_type = "previous"
        else:
            from_day = datetime.date(year=today.year, month=today.month, day=1)
            to_day = today
            update_type = "current"
        _logger.info(
            f"customer: {customer.name}/{customer.slug} metrics update for {update_type} month: {from_day} - {to_day}"
        )
        metrics = self._client.get_customer_metrics(toolchain_customer_id=customer.id, from_day=from_day, to_day=to_day)
        if not metrics:
            _logger.warning(f"No metrics for {customer.name}/{customer.slug}: {from_day} - {to_day}")
            return
        AmberfloCustomerMTDMetrics.update_or_create(
            customer_id=customer.id,
            customer_slug=customer.slug,
            date=from_day,
            cache_read_bytes=metrics.read_bytes,
            cache_write_bytes=metrics.write_bytes,
        )

    def on_reschedule(self, work_unit_payload: PeriodicallySyncAmberfloCustomer) -> datetime.datetime | None:
        return utcnow() + self._DEFAULT_SYNC_PERIOD


class AmberfloCustomerSyncCreator(Worker):
    work_unit_payload_cls = PeriodicallyCreateAmberfloCustomerSync

    def do_work(self, work_unit_payload: PeriodicallyCreateAmberfloCustomerSync) -> bool:
        since = utcnow() - datetime.timedelta(hours=24)
        # Not expecting this to reutrn a ton of data (since we only query for customers created in the last day)
        customers_qs = Customer.active_qs().filter(created_at__gte=since)
        customer_id_map = {customer.id: customer for customer in customers_qs}
        if not customer_id_map:
            return False
        existing_sync_qs = PeriodicallySyncAmberfloCustomer.objects.filter(customer_id__in=customer_id_map.keys())
        if existing_sync_qs.count() == len(customers_qs):
            # all the new customer IDs are already accounted for in PeriodicallySyncAmberfloCustomer.
            return False
        # This logic prefers to DB multiple DB roundtrip rather than try to load the PeriodicallySyncAmberfloCustomer into memory.
        # Since the customer_ids should be small, the number of roundtrips should also be small.
        new_sync_objects_count = 0
        for customer_id, customer in customer_id_map.items():
            _, created = PeriodicallySyncAmberfloCustomer.get_or_create(customer_id, customer_slug=customer.slug)
            if created:
                new_sync_objects_count += 1
        _logger.info(f"created {new_sync_objects_count} new sync objects for {len(customer_id_map)}")
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyCreateAmberfloCustomerSync) -> datetime.datetime:
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)
