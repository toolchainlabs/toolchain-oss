# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.payments.stripe_integration.client.webhook_client_test import (
    add_post_webhook_response,
    assert_post_webhook_request,
)
from toolchain.payments.stripe_integration.test_utils.utils import load_fixture
from toolchain.util.test.util import assert_messages


class TestStripeWebhookView:
    def _get_signature(self, data: str, secret) -> str:
        ts = int(utcnow().timestamp())
        mac_sigest = hmac.new(secret.encode(), msg=f"{ts}.{data}".encode(), digestmod=hashlib.sha256).hexdigest()
        return f"t={ts},v1={mac_sigest},v0=no-soup-for-you"

    def _assert_reject_webhook(self, caplog, reason: str) -> None:
        assert_messages(caplog, f"reject_stripe_webhook {reason=}")

    def test_stripe_webhook(self, client, settings, caplog, httpx_mock) -> None:
        add_post_webhook_response(httpx_mock)
        fixture = load_fixture("customer_updated_webhook")
        data = json.dumps(fixture)
        response = client.post(
            "/stripe/",
            content_type="application/json; charset=utf-8",
            data=data,
            HTTP_STRIPE_SIGNATURE=self._get_signature(data, secret=settings.STRIPE_WEBHOOK_ENDPOINT_SECRET),
        )
        assert response.status_code == 200
        assert_messages(caplog, match="Got Stripe webhook: customer.updated stripe_id=evt_1KtbV5Efbv3GSgSdnwJyjm2q")
        assert_post_webhook_request(httpx_mock.get_request())

    def test_stripe_webhook_no_signature(self, client, settings, caplog) -> None:
        fixture = load_fixture("customer_updated_webhook")
        data = json.dumps(fixture)
        response = client.post("/stripe/", content_type="application/json; charset=utf-8", data=data)
        assert response.status_code == 200
        self._assert_reject_webhook(caplog, "invalid_signature")

    def test_stripe_webhook_invalid_payload(self, client, settings, caplog) -> None:
        data = "Oh I gotta get on that internet, I'm late on everything!"
        response = client.post(
            "/stripe/",
            content_type="application/json; charset=utf-8",
            data=data,
            HTTP_STRIPE_SIGNATURE=self._get_signature(data, secret=settings.STRIPE_WEBHOOK_ENDPOINT_SECRET),
        )
        assert response.status_code == 200
        self._assert_reject_webhook(caplog, "invalid_payload")

    @pytest.mark.parametrize("method", ["GET", "HEAD", "DELETE", "PATCH", "PUT"])
    def test_stripe_webhook_invalid_method(self, client, method: str) -> None:
        response = client.generic(method, "/stripe/")
        assert response.status_code == 405
