# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from django.db.models import (
    AutoField,
    CharField,
    DateTimeField,
    IntegerField,
    PositiveBigIntegerField,
    PositiveSmallIntegerField,
)

from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.helpers import create_or_update_singleton
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.models import WorkUnitPayload

_logger = logging.getLogger(__name__)

transaction = TransactionBroker("amberflo_integration")


class PeriodicallySyncAmberfloCustomer(WorkUnitPayload):
    customer_id = CharField(max_length=22, editable=False)  # Toolchain(django/site/models.py:Customer id)
    # For Admin UI (toolshed) and __str__ display purposes only
    customer_slug = CharField(max_length=64, null=True)  # noqa: DJ01

    @classmethod
    def get_or_create(cls, customer_id: str, customer_slug: str) -> tuple[PeriodicallySyncAmberfloCustomer, bool]:
        psac, created = cls.objects.get_or_create(customer_id=customer_id, defaults={"customer_slug": customer_slug})
        if created:
            _logger.info(f"Created {psac}")
        else:
            psac.maybe_update_slug(customer_slug)
        return psac, created

    def maybe_update_slug(self, customer_slug: str) -> None:
        # temporary method to backfill slug for existing objects.
        if self.customer_slug == customer_slug:
            return
        self.customer_slug = customer_slug
        self.save()

    def __str__(self) -> str:
        return f"PeriodicallySyncAmberfloCustomer customer_id={self.customer_id}"

    @property
    def description(self) -> str:
        return str(self)


class PeriodicallyCreateAmberfloCustomerSync(WorkUnitPayload):
    period_minutes = IntegerField()

    @classmethod
    def create_or_update(cls, period_minutes: int | None) -> PeriodicallyCreateAmberfloCustomerSync:
        return create_or_update_singleton(cls, transaction, period_minutes=period_minutes)


class AmberfloCustomerMTDMetrics(ToolchainModel):
    """Month to date (MTD) metrics data for customers.

    We read this via the Amebrflo API so we can have the data locally to alert on and possibly display to customers.
    """

    id = AutoField(primary_key=True)  # we don't use it but django really wants it.
    customer_id = CharField(
        max_length=22, editable=False, db_index=True
    )  # Toolchain(django/site/models.py:Customer id)

    metric_year = PositiveSmallIntegerField(db_index=True)
    metric_month = PositiveSmallIntegerField(db_index=True)
    modified_at = DateTimeField(auto_now=True)
    cache_read_bytes = PositiveBigIntegerField()
    cache_write_bytes = PositiveBigIntegerField()

    # For Admin UI (toolshed) and __str__ display purposes only
    customer_slug = CharField(max_length=64)

    class Meta:
        unique_together = ("customer_id", "metric_year", "metric_month")

    @classmethod
    def update_or_create(
        cls, customer_id: str, customer_slug: str, date: datetime.date, cache_read_bytes: int, cache_write_bytes: int
    ) -> AmberfloCustomerMTDMetrics:
        cm, created = cls.objects.update_or_create(
            customer_id=customer_id,
            metric_year=date.year,
            metric_month=date.month,
            defaults=dict(
                cache_read_bytes=cache_read_bytes, cache_write_bytes=cache_write_bytes, customer_slug=customer_slug
            ),
        )
        _logger.info(f"customer_metrics for {customer_id=} {date=} {created=}")
        return cm

    @classmethod
    def get_metrics(cls, *, customer_id: str, year: int, month: int) -> AmberfloCustomerMTDMetrics | None:
        return cls.get_or_none(customer_id=customer_id, metric_year=year, metric_month=month)
