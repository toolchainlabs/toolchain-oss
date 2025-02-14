# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest

from toolchain.payments.stripe_integration.models import SubscribedCustomer
from toolchain.payments.stripe_integration.test_utils.utils import (
    add_create_customer_portal_session_response,
    assert_create_customer_portal_session_request,
    load_fixture,
)


@pytest.mark.django_db()
class TestStripeCustomerPortalView:
    def test_create_portal_session(self, responses, client) -> None:
        SubscribedCustomer.get_or_create(customer_id="frank", customer_slug="frank", stripe_customer_id="bob")
        add_create_customer_portal_session_response(responses)
        response = client.post(
            "/internal/api/v1/customers/frank/portal/", data={"return-url": "https://festivus.com/nbc/"}
        )
        assert response.status_code == 201
        assert response.json() == {
            "session_url": "https://newman-billing.com/session/no-soup-for-you",
            "stripe_customer_id": "bob",
        }
        assert len(responses.calls) == 1
        assert_create_customer_portal_session_request(
            responses.calls[0].request, stripe_customer_id="bob", return_url="https://festivus.com/nbc/"
        )

    def test_create_portal_session_no_subscribed_customer(self, client) -> None:
        response = client.post(
            "/internal/api/v1/customers/jerry/portal/", data={"return-url": "https://festivus.com/nbc/"}
        )
        assert response.status_code == 404


@pytest.mark.django_db()
class TestStripeProcessWebhookView:
    def test_subscription_updated(self, client) -> None:
        fixture = load_fixture("subscription_updated_webhook")
        response = client.post("/internal/api/v1/webhooks/", content_type="application/json", data=json.dumps(fixture))
        assert response.status_code == 201
