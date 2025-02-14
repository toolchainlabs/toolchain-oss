# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest

from toolchain.github_integration.client.app_clients import AppWebhookClient
from toolchain.github_integration.client.repo_clients_test import load_as_github_event
from toolchain.github_integration.common.records import GitHubEvent


class TestRepoWebhookClient:
    @pytest.fixture()
    def client(self, settings) -> AppWebhookClient:
        return AppWebhookClient.for_settings(settings)

    def test_post_github_webhook(self, httpx_mock, client: AppWebhookClient) -> None:
        httpx_mock.add_response(
            method="POST",
            url="http://scm-integration-api.tinsel.svc.cluster.local/api/v1/github/hooks/app/",
            json={"handled": False},
        )
        event_dict = load_as_github_event("installation_repositories_added", event_id="european")
        handled = client.post_github_webhook(event=GitHubEvent.from_json(event_dict))
        assert handled is False
        request = httpx_mock.get_request()
        request_json = json.loads(request.read())
        payload = request_json.pop("json_payload")
        assert request_json == {
            "event_type": "installation_repositories",
            "event_id": "european",
            "signature": "festivus",
            "new_signature": "festivus",
        }
        assert len(payload) == 6
        assert payload["installation"]["id"] == 7382407
        assert payload["sender"]["id"] == 1268088
