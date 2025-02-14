# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import httpx
from stripe import Event

from toolchain.payments.stripe_integration.client.common import get_http_client

_logger = logging.getLogger(__name__)


class StripeWebhooksClient:
    @classmethod
    def for_settings(cls, django_settings) -> StripeWebhooksClient:
        client = get_http_client(django_settings, url_prefix="/internal/api/v1/webhooks/")
        return cls(client=client)

    def __init__(self, *, client: httpx.Client) -> None:
        self._client = client

    def post_webhook(self, event: Event) -> None:
        response = self._client.post("", json=event.to_dict_recursive())
        response.raise_for_status()
