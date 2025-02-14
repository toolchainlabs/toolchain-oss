# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest
from jose import jwt

from toolchain.base.datetime_tools import utcnow
from toolchain.bitbucket_integration.app_client import BitBucketAppClient
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture


class TestBitBucketAppClient:
    @pytest.fixture()
    def app_client(self) -> BitBucketAppClient:
        return BitBucketAppClient(app_key="moles", secret="chicken", client_key="superman")

    def _add_api_response(self, httpx_mock, method: str, path: str, fixture_name: str):
        httpx_mock.add_response(method=method, url=f"https://api.bitbucket.org/{path}", json=load_fixture(fixture_name))

    def asset_auth(self, request) -> dict:
        header = request.headers["Authorization"]
        auth_type, _, token = header.partition(" ")
        assert auth_type == "JWT"
        claims = jwt.decode(token, key="chicken")
        assert claims["sub"] == "superman"
        assert claims["iss"] == "moles"
        now_ts = utcnow().timestamp()
        assert claims["iat"] == pytest.approx(now_ts, rel=2)
        assert claims["exp"] == pytest.approx(now_ts + 300, rel=2)
        return claims

    def test_list_repos(self, httpx_mock, app_client) -> None:
        self._add_api_response(httpx_mock, "GET", "2.0/repositories/festivus", "list_repos_response")
        repos_list = app_client.list_repos("festivus")
        request = httpx_mock.get_request()
        assert request.url == "https://api.bitbucket.org/2.0/repositories/festivus"
        self.asset_auth(request)
        assert len(repos_list) == 2
        assert repos_list[0].repo_id == "{73f69cff-bb55-4331-baa6-c62ed7cc01c2}"
        assert repos_list[0].name == "example-python"
        assert repos_list[0].slug == "example-python"
        assert repos_list[0].full_name == "festivus-miracle/example-python"
        assert repos_list[0].is_private is False

        assert repos_list[1].repo_id == "{c389eba6-ca13-49c5-8dec-4e617d39dffe}"
        assert repos_list[1].name == "minimal-pants"
        assert repos_list[1].slug == "minimal-pants"
        assert repos_list[1].full_name == "festivus-miracle/minimal-pants"
        assert repos_list[1].is_private is False
