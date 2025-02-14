# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest

from toolchain.github_integration.test_utils.fixtures_loader import load_fixture
from toolchain.util.test.util import convert_headers_to_wsgi


def load_fixture_to_request(fixture_name: str) -> tuple[dict, dict]:
    fixture = load_fixture(fixture_name)
    wsgi_headers = convert_headers_to_wsgi(fixture["headers"])
    return wsgi_headers, fixture["payload"]


@pytest.mark.django_db()
class TestGithubAppWebhookView:
    def test_github_webhook_no_data(self, client, caplog):
        response = client.post("/github/app/")
        assert caplog.records[0].message.startswith("reject_github_app_webhook reason='invalid_event'") is True
        assert response.status_code == 200

    def test_github_webhook_invalid_signature(self, client, httpx_mock, caplog) -> None:
        headers, payload = load_fixture_to_request("ping")
        response = client.post(
            "/github/app/",
            data=payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha1=festivus",
            HTTP_X_GITHUB_DELIVERY="no-soup-for-you-come-back-one-year",
            **headers,
        )
        assert caplog.records[-1].message.startswith("reject_github_app_webhook reason='invalid_signature'") is True
        assert response.status_code == 200
        assert httpx_mock.get_request() is None

    def test_github_webhook(self, httpx_mock, client) -> None:
        httpx_mock.add_response(
            method="POST",
            url="http://scm-integration-api.tinsel.svc.cluster.local:80/api/v1/github/hooks/app/",
            json={"handled": False},
        )
        headers, payload = load_fixture_to_request("installation")
        response = client.post(
            "/github/app/",
            data=payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE="sha1=fa54259792a2cadf2131ebd8932035b6434d2279",
            HTTP_X_HUB_SIGNATURE_256="sha256=46302266ed30be0f9e518edd2ef35cb9e976c5c9537ca9250d1030c1b28afd89",
            HTTP_X_GITHUB_DELIVERY="no-soup-for-you-come-back-one-year",
            **headers,
        )
        assert response.status_code == 200
        request = httpx_mock.get_request()
        assert request.method == "POST"
        req_json = json.loads(request.read())
        assert req_json["event_type"] == "installation"
        assert req_json["event_id"] == "no-soup-for-you-come-back-one-year"
        assert req_json["json_payload"]["installation"]["account"]["node_id"] == "MDEyOk9yZ2FuaXphdGlvbjM1NzUxNzk0"


class TestGithubRepoWebhookView:
    def _get_url_for_repo(self, github_repo_id: int) -> str:
        return f"http://scm-integration-api.tinsel.svc.cluster.local:80/api/v1/github/hooks/repos/{github_repo_id}/"

    def _add_webhook_secret(self, httpx_mock, github_repo_id: int, secret: str | None = None) -> None:
        url = self._get_url_for_repo(github_repo_id)
        if secret:
            httpx_mock.add_response(method="GET", url=url, json={"repo": {"name": "festivus", "secret": secret}})
        else:
            httpx_mock.add_response(method="GET", url=url, status_code=404)

    def _post_webhook(self, client, payload: dict, signature_sha1: str, signature_sha256: str, headers: dict[str, str]):
        response = client.post(
            "/github/repo/",
            data=payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE=f"sha1={signature_sha1}",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature_sha256}",
            HTTP_X_GITHUB_DELIVERY="no-soup-for-you-come-back-one-year",
            **headers,
        )
        return response

    def test_repo_webhook_no_secret(self, httpx_mock, client, caplog) -> None:
        self._add_webhook_secret(httpx_mock, 51405305)
        headers, payload = load_fixture_to_request("pull_request_assigned")
        response = self._post_webhook(client, payload, "festivus", "tinsel", headers)
        assert response.status_code == 200
        assert caplog.records[-1].message.startswith("reject_github_repo_webhook reason='no_secret'") is True
        assert httpx_mock.get_request() is not None

    def test_repo_webhook_invalid_signature(self, httpx_mock, client, caplog) -> None:
        self._add_webhook_secret(httpx_mock, 51405305, "chicken")
        headers, payload = load_fixture_to_request("pull_request_assigned")
        response = self._post_webhook(client, payload, "festivus", "tinsel", headers)
        assert response.status_code == 200
        assert caplog.records[-1].message.startswith("reject_github_repo_webhook reason='invalid_signature'") is True
        assert httpx_mock.get_request() is not None

    def test_github_webhook_no_repo_id(self, httpx_mock, client, caplog) -> None:
        headers, payload = load_fixture_to_request("pull_request_assigned")
        del payload["repository"]
        response = self._post_webhook(client, payload, "ac569dbaf2cee6a29f8816acfe8bf77afbeb5521", "xf3", headers)
        assert caplog.records[-1].message.startswith("reject_github_repo_webhook reason='missing_repo_id'") is True
        assert response.status_code == 200
        assert httpx_mock.get_request() is None

    def test_github_webhook_invalid_repo_id(self, httpx_mock, client, caplog) -> None:
        headers, payload = load_fixture_to_request("pull_request_assigned")
        payload["repository"]["id"] = "babka"
        response = self._post_webhook(client, payload, "ac569dbaf2cee6a29f8816acfe8bf77afbeb5521", "xf2", headers)
        assert caplog.records[-1].message.startswith("reject_github_repo_webhook reason='missing_repo_id'") is True
        assert response.status_code == 200
        assert httpx_mock.get_request() is None

    def test_github_webhook_empty_repo_id(self, httpx_mock, client, caplog) -> None:
        headers, payload = load_fixture_to_request("pull_request_assigned")
        payload["repository"]["id"] = 0
        response = self._post_webhook(client, payload, "ac569dbaf2cee6a29f8816acfe8bf77afbeb5521", "xf1", headers)
        assert caplog.records[-1].message.startswith("reject_github_repo_webhook reason='empty_repo_id'") is True
        assert response.status_code == 200
        assert httpx_mock.get_request() is None

    def test_repo_webhook(self, httpx_mock, client, caplog) -> None:
        repo_url = self._get_url_for_repo(51405305)
        self._add_webhook_secret(httpx_mock, 51405305, "chicken")
        httpx_mock.add_response(method="POST", url=repo_url, json={"handled": False})
        headers, payload = load_fixture_to_request("pull_request_assigned")
        response = self._post_webhook(
            client,
            payload,
            "ac569dbaf2cee6a29f8816acfe8bf77afbeb5521",
            "507a6906952c1005903559dc568a6a658d68c7ee35f82ecee6dc40d846246c6d",
            headers,
        )
        assert response.status_code == 200
        requests = httpx_mock.get_requests()
        assert len(requests) == 2
        assert requests[0].method == "GET"
        assert requests[1].method == "POST"
        req_json = json.loads(requests[1].read())
        assert req_json["event_type"] == "pull_request"
        assert req_json["event_id"] == "no-soup-for-you-come-back-one-year"
        assert req_json["json_payload"]["pull_request"]["user"]["node_id"] == "MDQ6VXNlcjEyNjgwODg="
