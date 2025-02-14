# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.payments.amberflo_integration.models import AmberfloCustomerMTDMetrics, PeriodicallySyncAmberfloCustomer
from toolchain.workflow.models import WorkUnit


@pytest.mark.django_db()
class TestPeriodicallySyncAmberfloCustomerModel:
    def test_create(self) -> None:
        assert PeriodicallySyncAmberfloCustomer.objects.count() == 0
        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id="newman", customer_slug="hello")
        assert PeriodicallySyncAmberfloCustomer.objects.count() == 1
        pssc = PeriodicallySyncAmberfloCustomer.objects.first()
        assert pssc.customer_id == "newman"
        assert pssc.customer_slug == "hello"
        assert pssc.work_unit.state == WorkUnit.READY

    def test_get_existing(self) -> None:
        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id="newman", customer_slug="hello")
        wu = PeriodicallySyncAmberfloCustomer.objects.first().work_unit
        now = utcnow()
        wu.take_lease(until=now + datetime.timedelta(minutes=20), last_attempt=now, node="happy-festivus")
        wu.work_succeeded(False)
        assert wu.state == WorkUnit.SUCCEEDED

        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id="newman", customer_slug="kramer")
        assert PeriodicallySyncAmberfloCustomer.objects.count() == 1
        pssc = PeriodicallySyncAmberfloCustomer.objects.first()
        assert pssc.customer_slug == "kramer"
        assert pssc.work_unit.state == WorkUnit.SUCCEEDED


@pytest.mark.django_db()
class TestAmberfloCustomerMTDMetricsModel:
    def test_create_new(self) -> None:
        assert AmberfloCustomerMTDMetrics.objects.count() == 0
        AmberfloCustomerMTDMetrics.update_or_create(
            customer_id="bob",
            customer_slug="kramer",
            date=datetime.date(2022, 3, 7),
            cache_read_bytes=97_111_000_506,
            cache_write_bytes=12_111_000_506,
        )
        assert AmberfloCustomerMTDMetrics.objects.count() == 1
        metrics = AmberfloCustomerMTDMetrics.objects.first()
        assert metrics.customer_id == "bob"
        assert metrics.customer_slug == "kramer"
        assert metrics.metric_year == 2022
        assert metrics.metric_month == 3
        assert metrics.modified_at.timestamp() == pytest.approx(utcnow().timestamp(), rel=2)
        assert metrics.cache_read_bytes == 97_111_000_506
        assert metrics.cache_write_bytes == 12_111_000_506

    def test_update_exiting(self) -> None:
        with freeze_time(datetime.datetime(2022, 7, 15, 14, 50, tzinfo=datetime.timezone.utc)):
            self.test_create_new()
        AmberfloCustomerMTDMetrics.update_or_create(
            customer_id="bob",
            customer_slug="kramer",
            date=datetime.date(2022, 3, 18),
            cache_read_bytes=111_000_506,
            cache_write_bytes=322_000_506,
        )
        assert AmberfloCustomerMTDMetrics.objects.count() == 1
        metrics = AmberfloCustomerMTDMetrics.objects.first()
        assert metrics.customer_id == "bob"
        assert metrics.customer_slug == "kramer"
        assert metrics.metric_year == 2022
        assert metrics.metric_month == 3
        assert metrics.modified_at.timestamp() == pytest.approx(utcnow().timestamp(), rel=2)
        assert metrics.cache_read_bytes == 111_000_506
        assert metrics.cache_write_bytes == 322_000_506
