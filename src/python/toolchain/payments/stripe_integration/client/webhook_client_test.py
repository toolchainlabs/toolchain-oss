# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
import stripe

from toolchain.payments.stripe_integration.client.webhook_client import StripeWebhooksClient
from toolchain.payments.stripe_integration.test_utils.utils import load_fixture

_DEFAULT_BASE_URL = "http://payments-api.tinsel.svc.cluster.local"


def load_event(fixture: str) -> stripe.Event:
    return stripe.Event.construct_from(load_fixture(fixture), key="jambalaya")


def add_post_webhook_response(httpx_mock) -> None:
    httpx_mock.add_response(method="POST", url=f"{_DEFAULT_BASE_URL}/internal/api/v1/webhooks/")


def assert_post_webhook_request(request) -> None:
    assert request.method == "POST"
    assert request.headers["user-agent"] == "Toolchain-Internal/fake-tc-service"
    assert request.headers["content-type"] == "application/json"
    assert request.url == "http://payments-api.tinsel.svc.cluster.local/internal/api/v1/webhooks/"
    event = stripe.Event.construct_from(json.loads(request.content), stripe.api_key)
    assert event


class TestSStripeWebhooksClient:
    @pytest.fixture()
    def client(self, settings) -> StripeWebhooksClient:
        return StripeWebhooksClient.for_settings(settings)

    def test_create_portal_session(self, httpx_mock, client: StripeWebhooksClient) -> None:
        add_post_webhook_response(httpx_mock)
        event = load_event("customer_updated_webhook")
        client.post_webhook(event)
        assert_post_webhook_request(httpx_mock.get_request())
