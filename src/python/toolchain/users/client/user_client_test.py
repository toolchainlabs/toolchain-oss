# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import httpx
import pytest

from toolchain.django.site.models import ToolchainUser
from toolchain.users.client.user_client import AuthProvider, UserClient

_DEFAULT_BASE_URL = "http://users-api.tinsel.svc.cluster.local"


def add_resolve_user_response(
    httpx_mock,
    user: ToolchainUser,
    customer_id: str,
    scm_user_id: str,
    scm_username: str,
    scm_provider: AuthProvider = AuthProvider.GITHUB,
) -> None:
    json_response = {
        "user": {
            "username": user.username,
            "scm_username": scm_username,
            "api_id": user.api_id,
            "scm": scm_provider.value,
        }
    }
    httpx_mock.add_response(
        url=f"{_DEFAULT_BASE_URL}/internal/api/v1/customers/{customer_id}/users/resolve/?user_id={scm_user_id}&scm={scm_provider.value}",
        json=json_response,
    )


def add_resolve_user_response_fail(
    httpx_mock, user: ToolchainUser, customer_id: str, github_user_id: str, status: int = 404
) -> None:
    httpx_mock.add_response(
        url=f"{_DEFAULT_BASE_URL}/internal/api/v1/customers/{customer_id}/users/resolve/?user_id={github_user_id}&scm=github",
        status_code=status,
    )


def add_get_admin_users_response(
    httpx_mock, customer_id: str, admins: tuple[tuple[str, str], ...] | None = None
) -> None:
    admins_json = [{"username": name, "email": email} for name, email in admins] if admins else []
    httpx_mock.add_response(
        url=f"{_DEFAULT_BASE_URL}/internal/api/v1/customers/{customer_id}/users/admin/",
        json={"admins": admins_json},
    )


@pytest.mark.django_db()
class TestUserClient:
    @pytest.fixture()
    def user(self):
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        return user

    @pytest.fixture()
    def client(self, settings, user: ToolchainUser) -> UserClient:
        return UserClient(
            service_name="mandelbaum", base_url=_DEFAULT_BASE_URL, customer_id="george", current_user=user
        )

    def _assert_resolve_ci_user_request(self, request, scm_userid: str, user: ToolchainUser) -> None:
        assert (
            request.url
            == f"http://users-api.tinsel.svc.cluster.local/internal/api/v1/customers/george/users/resolve/?user_id={scm_userid}&scm=github"
        )
        assert request.method == "GET"
        assert set(request.headers) == {
            "host",
            "accept",
            "accept-encoding",
            "connection",
            "user-agent",
            "remote-user",
            "x-toolchain-internal-call",
            "x-toolchain-internal-auth",
        }
        assert request.headers["user-agent"] == "Toolchain-Internal/mandelbaum"
        assert request.headers["x-toolchain-internal-call"] == "1"
        assert request.headers["x-toolchain-internal-auth"] == json.dumps({"user": {"api_id": user.api_id}})

    def test_resolve_ci_scm_user_legacy(self, user: ToolchainUser, client: UserClient, httpx_mock) -> None:
        httpx_mock.add_response(
            json={"user": {"username": "kenny", "github_username": "kennyk", "api_id": "kramer"}},
        )
        ci_user = client.resolve_ci_scm_user(scm_user_id="bob", scm=UserClient.Auth.GITHUB)
        assert ci_user is not None
        assert ci_user.api_id == "kramer"
        assert ci_user.username == "kenny"
        assert ci_user.scm_username == "kennyk"
        assert ci_user.scm == UserClient.Auth.GITHUB
        self._assert_resolve_ci_user_request(httpx_mock.get_request(), "bob", user)

    def test_resolve_ci_scm_user_new(self, user: ToolchainUser, client: UserClient, httpx_mock) -> None:
        httpx_mock.add_response(
            json={
                "user": {
                    "username": "kenny",
                    "scm_username": "kennyk",
                    "api_id": "kramer",
                    "scm": "github",
                    "github_username": "kennyk",
                }
            },
        )
        ci_user = client.resolve_ci_scm_user(scm_user_id="bob", scm=UserClient.Auth.GITHUB)
        assert ci_user is not None
        assert ci_user.api_id == "kramer"
        assert ci_user.username == "kenny"
        assert ci_user.scm_username == "kennyk"
        assert ci_user.scm == UserClient.Auth.GITHUB
        self._assert_resolve_ci_user_request(httpx_mock.get_request(), "bob", user)

    def test_resolve_ci_scm_user_not_found(self, user: ToolchainUser, client: UserClient, httpx_mock) -> None:
        httpx_mock.add_response(status_code=404)
        ci_user = client.resolve_ci_scm_user(scm_user_id="bob", scm=UserClient.Auth.GITHUB)
        assert ci_user is None
        self._assert_resolve_ci_user_request(httpx_mock.get_request(), "bob", user)

    def test_resolve_ci_scm_user_impersonation_not_allowed(
        self, user: ToolchainUser, client: UserClient, httpx_mock
    ) -> None:
        httpx_mock.add_response(status_code=403)
        ci_user = client.resolve_ci_scm_user(scm_user_id="bob", scm=UserClient.Auth.GITHUB)
        assert ci_user is None
        self._assert_resolve_ci_user_request(httpx_mock.get_request(), "bob", user)

    def test_resolve_ci_scm_user_internal_error(self, user: ToolchainUser, client: UserClient, httpx_mock) -> None:
        httpx_mock.add_response(status_code=500)  # we don't have error hadling code yet.
        with pytest.raises(httpx.HTTPStatusError, match="Server error '500 Internal Server Error' for url"):
            client.resolve_ci_scm_user(scm_user_id="kramer", scm=UserClient.Auth.GITHUB)
        self._assert_resolve_ci_user_request(httpx_mock.get_request(), "kramer", user)

    def test_get_admin_users(self, client: UserClient, httpx_mock) -> None:
        add_get_admin_users_response(httpx_mock, customer_id="george", admins=(("jerry", "jerry@cosmo.net"),))
        admins = client.get_admin_users()
        assert len(admins) == 1
        assert admins[0].username == "jerry"
        assert admins[0].email == "jerry@cosmo.net"
