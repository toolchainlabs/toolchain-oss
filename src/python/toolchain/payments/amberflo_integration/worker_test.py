# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time

from toolchain.django.site.models import Customer
from toolchain.payments.amberflo_integration.models import (
    AmberfloCustomerMTDMetrics,
    PeriodicallyCreateAmberfloCustomerSync,
    PeriodicallySyncAmberfloCustomer,
)
from toolchain.payments.amberflo_integration.test_utils.utils import (
    add_create_customer_response,
    add_search_customer_response,
    add_usage_batch_response,
    assert_customer_create_request,
    assert_customer_search_request,
    assert_get_usage_batch_request,
)
from toolchain.service.payments.workflow.dispatcher import PaymentsWorkDispatcher
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
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc.")

    @freeze_time(datetime.datetime(2022, 6, 4, tzinfo=datetime.timezone.utc))
    def test_sync_new_customer(self, httpx_mock, customer: Customer) -> None:
        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id=customer.id, customer_slug=customer.slug)
        add_search_customer_response(httpx_mock, is_empty=True, search_value=f"jambalaya_{customer.id}")
        add_create_customer_response(httpx_mock)
        add_usage_batch_response(httpx_mock, fixture="customer_metrics_response_no_data")
        assert self.do_work() == 1

        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        assert_customer_search_request(requests[0], search_value=f"jambalaya_{customer.id}")
        assert_customer_create_request(
            requests[1], customer_id=f"jambalaya_{customer.id}", customer_name="Jerry Seinfeld Inc."
        )
        assert_get_usage_batch_request(
            requests[2],
            customer_id=f"jambalaya_{customer.id}",
            start_timestamp=1654041600,
            end_timestamp=1654300800,
        )
        wu = PeriodicallySyncAmberfloCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        assert AmberfloCustomerMTDMetrics.objects.count() == 0

    def test_dont_sync_inactive_customer(self, customer: Customer) -> None:
        customer.deactivate()
        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id=customer.id, customer_slug=customer.slug)
        assert self.do_work() == 1
        wu = PeriodicallySyncAmberfloCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

    def _assert_metrics_data(self, customer: Customer, expected_modified_date: datetime.datetime) -> None:
        assert AmberfloCustomerMTDMetrics.objects.count() == 1
        metrics = AmberfloCustomerMTDMetrics.objects.first()
        assert metrics.customer_id == customer.id
        assert metrics.metric_year == 2022
        assert metrics.metric_month == 7
        assert metrics.modified_at == expected_modified_date
        assert metrics.cache_read_bytes == 19091441774
        assert metrics.cache_write_bytes == 3780459403

    @freeze_time(datetime.datetime(2022, 7, 13, 14, 50, tzinfo=datetime.timezone.utc))
    def test_sync_existing_customer_middle_month_metrics(self, httpx_mock, customer: Customer) -> None:
        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id=customer.id, customer_slug=customer.slug)
        add_search_customer_response(httpx_mock, is_empty=False, search_value=f"jambalaya_{customer.id}")
        add_usage_batch_response(httpx_mock, fixture="customer_metrics_response_1")
        assert self.do_work() == 1
        reqs = httpx_mock.get_requests()
        assert_customer_search_request(reqs[0], search_value=f"jambalaya_{customer.id}")

        assert_get_usage_batch_request(
            reqs[1],
            customer_id=f"jambalaya_{customer.id}",
            start_timestamp=1656633600,
            end_timestamp=1657670400,
        )
        wu = PeriodicallySyncAmberfloCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        self._assert_metrics_data(customer, datetime.datetime(2022, 7, 13, 14, 50, tzinfo=datetime.timezone.utc))

    @freeze_time(datetime.datetime(2022, 8, 1, 0, 50, tzinfo=datetime.timezone.utc))
    def test_sync_existing_customer_middle_month_start(self, httpx_mock, customer: Customer) -> None:
        PeriodicallySyncAmberfloCustomer.get_or_create(customer_id=customer.id, customer_slug=customer.slug)
        add_search_customer_response(httpx_mock, is_empty=False, search_value=f"jambalaya_{customer.id}")
        add_usage_batch_response(httpx_mock, fixture="customer_metrics_response_1")
        assert self.do_work() == 1
        reqs = httpx_mock.get_requests()
        assert_customer_search_request(reqs[0], search_value=f"jambalaya_{customer.id}")

        assert_get_usage_batch_request(
            reqs[1],
            customer_id=f"jambalaya_{customer.id}",
            start_timestamp=1656633600,
            end_timestamp=1659312000,
        )
        wu = PeriodicallySyncAmberfloCustomer.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        self._assert_metrics_data(customer, datetime.datetime(2022, 8, 1, 0, 50, tzinfo=datetime.timezone.utc))


class TestStripeCustomerSyncCreator(BaseWorkerTests):
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="usps", name="Postal Service", customer_type=Customer.Type.PROSPECT)

    def test_no_recent_customers(self, customer: Customer) -> None:
        customer.created_at = datetime.datetime(2022, 6, 10, tzinfo=datetime.timezone.utc)
        customer.save()
        PeriodicallyCreateAmberfloCustomerSync.create_or_update(period_minutes=122)
        assert self.do_work() == 1
        self._assert_sync_state()
        assert PeriodicallySyncAmberfloCustomer.objects.count() == 0

    def test_recent_customers(self, customer: Customer) -> None:
        PeriodicallyCreateAmberfloCustomerSync.create_or_update(period_minutes=122)
        assert self.do_work() == 1
        self._assert_sync_state()
        assert PeriodicallySyncAmberfloCustomer.objects.count() == 1
        sync = PeriodicallySyncAmberfloCustomer.objects.first()
        assert sync.customer_id == customer.id

    def test_recent_customers_already_sinced(self, customer: Customer) -> None:
        pssc, created = PeriodicallySyncAmberfloCustomer.get_or_create(customer.id, customer_slug=customer.slug)
        mark_work_unit_success(pssc)
        assert created is True
        PeriodicallyCreateAmberfloCustomerSync.create_or_update(period_minutes=122)
        assert self.do_work() == 1
        self._assert_sync_state()
        assert PeriodicallySyncAmberfloCustomer.objects.count() == 1

    def _assert_sync_state(self):
        assert PeriodicallyCreateAmberfloCustomerSync.objects.count() == 1
        wu = PeriodicallyCreateAmberfloCustomerSync.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
