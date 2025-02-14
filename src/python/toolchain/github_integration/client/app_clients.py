# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import httpx

from toolchain.github_integration.client.common import get_http_client
from toolchain.github_integration.common.records import GitHubEvent

_logger = logging.getLogger(__name__)


class AppWebhookClient:
    @classmethod
    def for_settings(cls, django_settings) -> AppWebhookClient:
        client = get_http_client(django_settings, url_prefix="api/v1/")
        return cls(client)

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def post_github_webhook(self, *, event: GitHubEvent) -> bool:
        # See github_integration/api/urls.py
        response = self._client.post("github/hooks/app/", json=event.to_json_dict())
        response.raise_for_status()
        return response.json()["handled"]
