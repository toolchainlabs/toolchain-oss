# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import httpx

from toolchain.bitbucket_integration.client.common import get_http_client
from toolchain.bitbucket_integration.common.events import AppInstallEvent, AppUninstallEvent, WebhookEvent

_logger = logging.getLogger(__name__)


class AppClient:
    @classmethod
    def for_settings(cls, django_settings) -> AppClient:
        client = get_http_client(django_settings)
        return cls(client=client)

    def __init__(self, *, client: httpx.Client) -> None:
        self._client = client

    def app_install(self, app_install: AppInstallEvent) -> bool:
        # See bitbucket_integration/api/urls.py
        response = self._client.post("api/v1/bitbucket/app/install/", json=app_install.to_json_dict())
        if response.status_code == 404:
            _logger.warning(f"Didn't install bitbucket app for account_name={app_install.account_name}")
            return False
        response.raise_for_status()
        return True

    def app_uninstall(self, app_uninstall: AppUninstallEvent) -> bool:
        # See bitbucket_integration/api/urls.py
        response = self._client.patch("api/v1/bitbucket/app/install/", json=app_uninstall.to_json_dict())
        if response.status_code == 404:
            _logger.warning(f"Didn't uninstall bitbucket app for account_name={app_uninstall.account_name}")
            return False
        response.raise_for_status()
        return True

    def send_webhook(self, webhook: WebhookEvent) -> bool:
        # See bitbucket_integration/api/urls.py
        response = self._client.post(url="api/v1/bitbucket/webhook/", json=webhook.to_json_dict())
        response.raise_for_status()
        return True
