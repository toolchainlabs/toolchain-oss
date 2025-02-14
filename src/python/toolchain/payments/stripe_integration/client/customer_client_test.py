# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from urllib.parse import parse_qsl

import pytest

from toolchain.payments.stripe_integration.client.customer_client import StripeCustomerClient

_DEFAULT_BASE_URL = "http://payments-api.tinsel.svc.cluster.local"


def add_create_portal_session_response(
    httpx_mock, customer_id: str, session_url: str | None = "https://newman-billing.com/session/no-soup-for-you"
) -> None:
    url = f"{_DEFAULT_BASE_URL}/internal/api/v1/customers/{customer_id}/portal/"
    if session_url:
        httpx_mock.add_response(method="POST", url=url, json={"session_url": session_url})
    else:
        httpx_mock.add_response(method="POST", url=url, status_code=404)


def assert_create_portal_session_request(request, customer_id: str, return_url: str) -> None:
    assert request.method == "POST"
    assert request.headers["user-agent"] == "Toolchain-Internal/fake-tc-service"
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert (
        request.url == f"http://payments-api.tinsel.svc.cluster.local/internal/api/v1/customers/{customer_id}/portal/"
    )
    assert dict(parse_qsl(request.content.decode())) == {"return-url": return_url}


class TestStripeCustomerClient:
    @pytest.fixture()
    def client(self, settings) -> StripeCustomerClient:
        return StripeCustomerClient.for_customer(settings, customer_id="costanza")

    def test_create_portal_session(self, httpx_mock, client: StripeCustomerClient) -> None:
        add_create_portal_session_response(httpx_mock, customer_id="costanza")
        session_url = client.create_portal_session(return_url="https://soup.jerry/crab")
        assert session_url == "https://newman-billing.com/session/no-soup-for-you"
        request = httpx_mock.get_request()
        assert_create_portal_session_request(request, customer_id="costanza", return_url="https://soup.jerry/crab")

    def test_create_portal_session_no_customer(self, httpx_mock, client: StripeCustomerClient) -> None:
        add_create_portal_session_response(httpx_mock, customer_id="costanza", session_url=None)
        assert client.create_portal_session(return_url="https://soup.jerry/crab") is None
        request = httpx_mock.get_request()
        assert_create_portal_session_request(request, customer_id="costanza", return_url="https://soup.jerry/crab")
