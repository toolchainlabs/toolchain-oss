# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from httpx import ReadTimeout

from toolchain.payments.amberflo_integration.amberflo_client import AmberfloCustomersClient, AmberfloTransientError
from toolchain.payments.amberflo_integration.test_utils.utils import (
    AMBERFLO_DOMAIN,
    add_create_customer_response,
    add_search_customer_response,
    add_usage_batch_response,
    assert_customer_create_request,
    assert_customer_search_request,
    assert_get_usage_batch_request,
)


class TestAmberfloCustomersClient:
    @pytest.fixture()
    def client(self) -> AmberfloCustomersClient:
        return AmberfloCustomersClient(env_name="festivus", api_key="yoyoma")

    def test_get_customer(self, httpx_mock, client: AmberfloCustomersClient) -> None:
        add_search_customer_response(httpx_mock, search_value="festivus_puddy", is_empty=False)
        customer = client.get_customer(toolchain_customer_id="puddy")
        assert customer is not None
        assert customer.name == "No soup for you"
        assert customer.customer_id == "dev_asher_jerry_123"
        assert customer.update_time == datetime.datetime(2022, 6, 7, 16, 59, 37, 938000, tzinfo=datetime.timezone.utc)
        assert_customer_search_request(httpx_mock.get_request(), search_value="festivus_puddy")

    def test_get_customer_no_customer(self, httpx_mock, client: AmberfloCustomersClient) -> None:
        add_search_customer_response(httpx_mock, search_value="festivus_puddy", is_empty=True)
        customer = client.get_customer(toolchain_customer_id="puddy")
        assert customer is None
        assert_customer_search_request(httpx_mock.get_request(), search_value="festivus_puddy")

    def test_create_customer(self, httpx_mock, client: AmberfloCustomersClient) -> None:
        add_create_customer_response(httpx_mock)
        customer = client.create_customer(toolchain_customer_id="david", name="David Puddy")
        assert customer.name == "No soup for you"
        assert customer.customer_id == "dev_asher_jerry_123"
        assert customer.update_time == datetime.datetime(2022, 6, 7, 16, 59, 37, 938000, tzinfo=datetime.timezone.utc)
        assert_customer_create_request(
            httpx_mock.get_request(), customer_id="festivus_david", customer_name="David Puddy"
        )

    def test_get_customer_metrics(self, httpx_mock, client: AmberfloCustomersClient) -> None:
        add_usage_batch_response(httpx_mock, fixture="customer_metrics_response_1")
        metrics = client.get_customer_metrics(
            toolchain_customer_id="frankCostanza",
            from_day=datetime.datetime(2022, 7, 1, tzinfo=datetime.timezone.utc),
            to_day=datetime.datetime(2022, 7, 2, tzinfo=datetime.timezone.utc),
        )
        assert metrics is not None
        assert metrics.write_bytes == 3780459403
        assert metrics.read_bytes == 19091441774
        assert metrics.num_write_blobs == 180198
        assert metrics.num_read_blobs == 534780

        assert_get_usage_batch_request(
            httpx_mock.get_request(),
            customer_id="festivus_frankCostanza",
            start_timestamp=1656633600,
            end_timestamp=1656720000,
        )

    def test_get_customer_metrics_empty(self, httpx_mock, client: AmberfloCustomersClient) -> None:
        add_usage_batch_response(httpx_mock, fixture="customer_metrics_response_no_data")
        metrics = client.get_customer_metrics(
            toolchain_customer_id="frankCostanza",
            from_day=datetime.datetime(2022, 7, 1, tzinfo=datetime.timezone.utc),
            to_day=datetime.datetime(2022, 7, 2, tzinfo=datetime.timezone.utc),
        )
        assert metrics is None

    def test_get_customer_network_error(self, httpx_mock, client: AmberfloCustomersClient) -> None:
        httpx_mock.add_exception(
            ReadTimeout("no soup for you"),
            method="POST",
            url=f"https://{AMBERFLO_DOMAIN}/usage/batch",
        )
        with pytest.raises(AmberfloTransientError, match="network error: ReadTimeout.*no soup for you"):
            client.get_customer_metrics(
                toolchain_customer_id="frankCostanza",
                from_day=datetime.datetime(2022, 7, 1, tzinfo=datetime.timezone.utc),
                to_day=datetime.datetime(2022, 7, 2, tzinfo=datetime.timezone.utc),
            )

        assert_get_usage_batch_request(
            httpx_mock.get_request(),
            customer_id="festivus_frankCostanza",
            start_timestamp=1656633600,
            end_timestamp=1656720000,
        )

    @pytest.mark.parametrize("http_status", [501, 500, 503, 504])
    def test_get_customer_trainsient_http_error(
        self, httpx_mock, http_status: int, client: AmberfloCustomersClient
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=f"https://{AMBERFLO_DOMAIN}/usage/batch", status_code=http_status, text="he took it out"
        )
        with pytest.raises(AmberfloTransientError, match=f"HTTP error {http_status}"):
            client.get_customer_metrics(
                toolchain_customer_id="frankCostanza",
                from_day=datetime.datetime(2022, 7, 1, tzinfo=datetime.timezone.utc),
                to_day=datetime.datetime(2022, 7, 2, tzinfo=datetime.timezone.utc),
            )

        assert_get_usage_batch_request(
            httpx_mock.get_request(),
            customer_id="festivus_frankCostanza",
            start_timestamp=1656633600,
            end_timestamp=1656720000,
        )
