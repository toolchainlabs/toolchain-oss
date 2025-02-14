# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.django.site.models import Customer
from toolchain.users.models import (
    PeriodicallyExportCustomers,
    PeriodicallyExportRemoteWorkerTokens,
    RemoteExecWorkerToken,
)
from toolchain.users.workers.users_worker import UsersWorkDispatcher
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests


@pytest.mark.django_db()
class TestPeriodicallyExportCustomers(BaseWorkflowWorkerTests):
    _BUCKET = "festivus-bucket"

    def get_dispatcher(self) -> type[UsersWorkDispatcher]:
        return UsersWorkDispatcher

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def customers(self) -> list[Customer]:
        return [
            Customer.create(slug="jerry", name="Jerry Seinfeld Inc"),
            Customer.create(slug="whatley", name="Tim Whatley"),
            Customer.create(slug="ovaltine", name="Ovaltine!"),
        ]

    def _assert_customers(self, customers: list[Customer]) -> None:
        content, content_type = S3().get_content_with_type(bucket=self._BUCKET, key="seinfeld/gold/customers.json")
        assert content_type == "application/json"
        assert json.loads(content) == {
            customers[0].id: "jerry",
            customers[1].id: "whatley",
            customers[2].id: "ovaltine",
        }

    def test_do_work_once(self, customers: list[Customer]) -> None:
        PeriodicallyExportCustomers.create_or_update(period_minutes=None)
        assert self.do_work() == 1
        wu = PeriodicallyExportCustomers.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        self._assert_customers(customers)

    def test_periodic(self, customers: list[Customer]) -> None:
        PeriodicallyExportCustomers.create_or_update(period_minutes=130)
        assert self.do_work() == 1
        wu = PeriodicallyExportCustomers.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        self._assert_customers(customers)


@pytest.mark.django_db()
class TestPeriodicRemoteWorkerTokensExporter(BaseWorkflowWorkerTests):
    _BUCKET = "festivus-bucket"

    def get_dispatcher(self) -> type[UsersWorkDispatcher]:
        return UsersWorkDispatcher

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def tokens(self) -> list[RemoteExecWorkerToken]:
        return [
            RemoteExecWorkerToken.create(
                customer_id="jerry", user_api_id="constanza", customer_slug="seinfeld", description="no soup for you"
            ),
            RemoteExecWorkerToken.create(
                customer_id="jerry",
                user_api_id="george",
                customer_slug="seinfeld",
                description="It's not a lie if you belive it",
            ),
            RemoteExecWorkerToken.create(
                customer_id="newman",
                user_api_id="constanza",
                customer_slug="usps",
                description="Have you seen the DMV?",
            ),
            RemoteExecWorkerToken.create(
                customer_id="newman", user_api_id="cosmo", customer_slug="usps", description="yo yo ma"
            ),
            RemoteExecWorkerToken.create(
                customer_id="kramer",
                user_api_id="cosmo",
                customer_slug="kramerica",
                description="Festivus for the rest of us",
            ),
        ]

    def _assert_export(self, tokens: list[RemoteExecWorkerToken]):
        tokens_json = json.loads(S3().get_content("festivus-bucket", "newman/tokens.json"))
        assert len(tokens_json) == len(tokens)
        assert set(tokens_json.keys()) == {rw_token.token for rw_token in tokens}

    def test_do_work_once(self, tokens: list[RemoteExecWorkerToken]) -> None:
        PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=None)
        assert self.do_work() == 1
        wu = PeriodicallyExportRemoteWorkerTokens.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        self._assert_export(tokens)

    def test_periodic(self, tokens: list[RemoteExecWorkerToken]) -> None:
        PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=90)
        assert self.do_work() == 1
        wu = PeriodicallyExportRemoteWorkerTokens.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        self._assert_export(tokens)
