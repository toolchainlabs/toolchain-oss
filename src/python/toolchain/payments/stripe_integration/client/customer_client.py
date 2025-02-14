# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import httpx

from toolchain.payments.stripe_integration.client.common import get_http_client

_logger = logging.getLogger(__name__)


class StripeCustomerClient:
    @classmethod
    def for_customer(cls, django_settings, *, customer_id: str) -> StripeCustomerClient:
        client = get_http_client(django_settings, url_prefix=f"/internal/api/v1/customers/{customer_id}/")
        return cls(client=client, customer_id=customer_id)

    def __init__(self, *, client: httpx.Client, customer_id: str) -> None:
        self._client = client
        self._customer_id = customer_id

    def create_portal_session(self, return_url: str) -> str | None:
        response = self._client.post("portal/", data={"return-url": return_url})
        if response.status_code == 404:
            _logger.warning(f"Can't create session for customer: {self._customer_id}")
            return None
        # TODO: Error handling
        response.raise_for_status()
        return response.json()["session_url"]
