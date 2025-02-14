# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from toolchain.bitbucket_integration.client.app_clients import AppClient
from toolchain.bitbucket_integration.common.events import AppInstallEvent, AppUninstallEvent, WebhookEvent

_BASE_URL = "http://scm-integration-api.tinsel.svc.cluster.local:80"


def add_install_response(httpx_mock, status_code: int = 200) -> None:
    httpx_mock.add_response(method="POST", status_code=status_code, url=f"{_BASE_URL}/api/v1/bitbucket/app/install/")


def add_uninstall_response(httpx_mock, status_code: int = 200) -> None:
    httpx_mock.add_response(method="PATCH", status_code=status_code, url=f"{_BASE_URL}/api/v1/bitbucket/app/install/")


def add_webhook_response(httpx_mock) -> None:
    httpx_mock.add_response(method="POST", url=f"{_BASE_URL}/api/v1/bitbucket/webhook/")


class TestRepoWebhookClient:
    _BASE_URL = "http://jerry.repo-service.local"

    @pytest.fixture()
    def client(self, settings) -> AppClient:
        return AppClient.for_settings(django_settings=settings)

    @pytest.fixture()
    def app_install_event(self) -> AppInstallEvent:
        return AppInstallEvent(
            account_name="bagels",
            account_type="team",
            account_url="https:/no-soup-for.you",
            account_id="h&h",
            client_key="no-bagels",
            shared_secret="Yama Hama it's Fright Night.",
            jwt="freckles",
        )

    @pytest.fixture()
    def app_uninstall_event(self) -> AppUninstallEvent:
        return AppUninstallEvent(
            account_name="No Bagels",
            account_type="team",
            account_url="https:/no-soup-for.you",
            account_id="h&h",
            client_key="no-bagels",
            jwt="freckles",
        )

    @pytest.fixture()
    def webhook_event(self) -> WebhookEvent:
        payload = {"soup": "no soup for you"}
        return WebhookEvent(
            event_type="pullrequest:created",
            event_id="jerry-seinfeld",
            hook_id="newman",
            attempt_number=1,
            jwt=None,
            payload=json.dumps(payload).encode(),
            json_payload=payload,
        )

    def test_for_settings(self) -> None:
        mock_settings = MagicMock(IS_RUNNING_ON_K8S=True, NAMESPACE="jambalaya")
        client = AppClient.for_settings(mock_settings)
        assert client._client.base_url == "http://scm-integration-api.jambalaya.svc.cluster.local:80/"

    def test_app_install_team(self, app_install_event: AppInstallEvent, client: AppClient, httpx_mock) -> None:
        add_install_response(httpx_mock)
        assert client.app_install(app_install_event) is True
        request = httpx_mock.get_request()
        assert json.loads(request.read()) == {
            "account_name": "bagels",
            "account_id": "h&h",
            "account_type": "team",
            "account_url": "https:/no-soup-for.you",
            "client_key": "no-bagels",
            "shared_secret": "Yama Hama it's Fright Night.",
            "jwt": "freckles",
        }

    def test_app_install_not_installed(self, app_install_event: AppInstallEvent, client: AppClient, httpx_mock) -> None:
        add_install_response(httpx_mock, status_code=404)
        assert client.app_install(app_install_event) is False
        assert httpx_mock.get_request() is not None

    def test_app_uninstall_team(self, app_uninstall_event: AppUninstallEvent, client: AppClient, httpx_mock) -> None:
        add_uninstall_response(httpx_mock)
        assert client.app_uninstall(app_uninstall_event) is True
        request = httpx_mock.get_request()
        assert json.loads(request.read()) == {
            "account_name": "No Bagels",
            "account_id": "h&h",
            "account_type": "team",
            "account_url": "https:/no-soup-for.you",
            "client_key": "no-bagels",
            "jwt": "freckles",
        }

    def test_app_uninstall_no_op(self, app_uninstall_event: AppUninstallEvent, client: AppClient, httpx_mock) -> None:
        add_uninstall_response(httpx_mock, status_code=404)
        assert client.app_uninstall(app_uninstall_event) is False
        assert httpx_mock.get_request() is not None

    def test_webhook(self, webhook_event: WebhookEvent, client: AppClient, httpx_mock) -> None:
        add_webhook_response(httpx_mock)
        assert client.send_webhook(webhook_event) is True
        request_json = json.loads(httpx_mock.get_request().read())
        assert request_json == {
            "event_type": "pullrequest:created",
            "event_id": "jerry-seinfeld",
            "hook_id": "newman",
            "jwt": None,
            "attempt_number": 1,
            "json_payload": {"soup": "no soup for you"},
        }
