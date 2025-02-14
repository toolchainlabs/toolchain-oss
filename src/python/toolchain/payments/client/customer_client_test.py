# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.payments.client.customer_client import PaymentsCustomerClient

_DEFAULT_BASE_URL = "http://payments-api.tinsel.svc.cluster.local"


def add_get_plan_and_usage_response(
    httpx_mock,
    customer_id: str,
    with_usage: bool = True,
    with_plan: bool = True,
    plan_name: str = "Festivus Mircale",
    trial_end_date: str = "2023-04-25",
) -> None:
    url = f"{_DEFAULT_BASE_URL}/internal/api/v1/customers/{customer_id}/info/"
    httpx_mock.add_response(
        method="GET",
        url=url,
        json={
            "usage": {"read_bytes": 111000506, "write_bytes": 322000506} if with_usage else {},
            "plan": {"name": plan_name, "price": "no soup for you", "trial_end": trial_end_date} if with_plan else {},
        },
    )


def assert_get_plan_and_usage_request(request, customer_id: str) -> None:
    assert request.method == "GET"
    assert request.headers["user-agent"] == "Toolchain-Internal/fake-tc-service"
    assert request.url == f"http://payments-api.tinsel.svc.cluster.local/internal/api/v1/customers/{customer_id}/info/"


class TestStripeCustomerClient:
    @pytest.fixture()
    def client(self, settings) -> PaymentsCustomerClient:
        return PaymentsCustomerClient.for_customer(settings, customer_id="costanza")

    def test_get_plan_and_usage(self, httpx_mock, client: PaymentsCustomerClient) -> None:
        add_get_plan_and_usage_response(httpx_mock, customer_id="costanza")
        ps = client.get_plan_and_usage()
        assert ps.cache_read_bytes == 111000506
        assert ps.cache_write_bytes == 322000506
        assert ps.plan == "Festivus Mircale"
        assert ps.price == "no soup for you"
        assert ps.trial_end == datetime.date(2023, 4, 25)
        assert_get_plan_and_usage_request(httpx_mock.get_request(), "costanza")

    def test_get_plan_and_usage_no_data(self, httpx_mock, client: PaymentsCustomerClient) -> None:
        add_get_plan_and_usage_response(httpx_mock, customer_id="costanza", with_plan=False, with_usage=False)
        ps = client.get_plan_and_usage()
        assert ps.cache_read_bytes is None
        assert ps.cache_write_bytes is None
        assert ps.plan == "N/A"
        assert ps.price == "N/A"
        assert ps.trial_end is None
        assert_get_plan_and_usage_request(httpx_mock.get_request(), "costanza")
