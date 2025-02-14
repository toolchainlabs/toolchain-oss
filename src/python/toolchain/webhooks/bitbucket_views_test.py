# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

from toolchain.bitbucket_integration.client.app_clients_test import (
    add_install_response,
    add_uninstall_response,
    add_webhook_response,
)
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture
from toolchain.util.test.util import assert_messages, convert_headers_to_wsgi


def test_app_descriptor_view(client) -> None:
    response = client.get("/bitbucket/descriptor/")
    assert response.status_code == 200
    assert response.json() == {
        "key": "toolchain",
        "name": "Toolchain",
        "description": "Toolchain Build system",
        "vendor": {"name": "Toolchain Labs", "url": "https://www.toolchain.com/"},
        "baseUrl": "https://jambalaya.seinfeld.george",
        "authentication": {"type": "jwt"},
        "lifecycle": {"installed": "/bitbucket/app/install/", "uninstalled": "/bitbucket/app/uninstall/"},
        "modules": {"webhooks": [{"event": "*", "url": "/bitbucket/webhook/"}]},
        "scopes": ["account", "repository", "pullrequest"],
        "contexts": ["account"],
    }


def _post_fixture(client, path: str, fixture_name: str):
    fixture = load_fixture(fixture_name)
    headers = convert_headers_to_wsgi(fixture["headers"])
    resp = client.post(path, data=json.dumps(fixture["payload"]), content_type="application/json", **headers)
    return resp


def test_install_app_view_team(client, httpx_mock) -> None:
    add_install_response(httpx_mock)
    response = _post_fixture(client, "/bitbucket/app/install/", "app_install_team")
    assert response.status_code == 200


def test_install_app_view_user(client, httpx_mock) -> None:
    add_install_response(httpx_mock)
    response = _post_fixture(client, "/bitbucket/app/install/", "app_install_user")
    assert response.status_code == 200


def test_install_app_view_unknown_type(client, httpx_mock, caplog) -> None:
    add_install_response(httpx_mock)
    fixture = load_fixture("app_install_user")
    fixture["payload"]["principal"]["type"] = "bagels"
    headers = convert_headers_to_wsgi(fixture["headers"])
    response = client.post(
        "/bitbucket/app/install/", data=json.dumps(fixture["payload"]), content_type="application/json", **headers
    )
    assert response.status_code == 200
    assert_messages(caplog, "AppInstallEvent: Unknown bitbucket account type")


def test_install_app_view_no_jwt(client, caplog, httpx_mock) -> None:
    fixture = load_fixture("app_install_team")
    del fixture["headers"]["Authorization"]
    headers = convert_headers_to_wsgi(fixture["headers"])
    response = client.post(
        "/bitbucket/app/install/", data=json.dumps(fixture["payload"]), content_type="application/json", **headers
    )
    assert response.status_code == 200
    assert httpx_mock.get_request() is None
    assert caplog.records[-1].message.startswith("reject_bitbucket webhook=app_install reason='jwt_error'")


def test_uninstall_app_view_team(client, httpx_mock) -> None:
    add_uninstall_response(httpx_mock)
    response = _post_fixture(client, "/bitbucket/app/uninstall/", "app_uninstall_team")
    assert response.status_code == 200


def test_uninstall_app_view_user(client, httpx_mock) -> None:
    add_uninstall_response(httpx_mock)
    response = _post_fixture(client, "/bitbucket/app/uninstall/", "app_uninstall_user")
    assert response.status_code == 200


def test_uninstall_app_view_no_jwt(client, caplog, httpx_mock) -> None:
    fixture = load_fixture("app_uninstall_team")
    del fixture["headers"]["Authorization"]
    headers = convert_headers_to_wsgi(fixture["headers"])
    response = client.post(
        "/bitbucket/app/uninstall/", data=json.dumps(fixture["payload"]), content_type="application/json", **headers
    )
    assert response.status_code == 200
    assert httpx_mock.get_request() is None
    assert caplog.records[-1].message.startswith("reject_bitbucket webhook=app_uninstall reason='jwt_error'")


def test_webhook_view(client, httpx_mock) -> None:
    add_webhook_response(httpx_mock)
    response = _post_fixture(client, "/bitbucket/webhook/", "pullrequest_created")
    assert response.status_code == 200
