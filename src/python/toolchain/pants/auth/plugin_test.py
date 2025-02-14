# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from pants.option.global_options import AuthPluginResult, AuthPluginState
from requests.exceptions import SSLError

from toolchain.pants.auth.plugin import toolchain_auth_plugin
from toolchain.util.test.util import assert_messages

TEST_TOKEN_STRING = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1OTAxNzk1ODgiLCJ0eXAiOiJKV1QifQ.eyJleHAiOiAxODkzNDg0ODAwLCAiaXNzIjogInRvb2xjaGFpbiIsICJpYXQiOiAxNTk5Njc5NzM4LCAiYXVkIjogWyJidWlsZHNlbnNlIiwgImRlcGVuZGVuY3kiLCAiaW1wZXJzb25hdGUiXSwgInVzZXJuYW1lIjogImFzaGVyIiwgInR5cGUiOiAiYWNjZXNzIiwgInRvb2xjaGFpbl9jbGFpbXNfdmVyIjogMiwgInRvb2xjaGFpbl91c2VyIjogImZRNkFOcXUyczlHd0F2SENKempjZ0EiLCAidG9vbGNoYWluX3JlcG8iOiAiS1hMc1NYZTlaTVR5RzJkY1d2ckxxbiIsICJ0b29sY2hhaW5fY3VzdG9tZXIiOiAiaGR0MmhuaVVYZW1zYUhEdWlCYXA0QiJ9.urUjGZCtAApqVgBA3Pa0hElHwAdZBEW6Iw8ZjmEgkyw"


def create_prior_result(
    *, state: AuthPluginState, instance_name: str, token: str | None, expiration: datetime.datetime | None
) -> AuthPluginResult:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return AuthPluginResult(
        state=state,  # type: ignore[call-arg]
        execution_headers=headers,  # type: ignore[call-arg]
        store_headers=headers,  # type: ignore[call-arg]
        instance_name=instance_name,
        expiration=expiration,
    )


class FakeOptions:
    def __init__(self, repo: str | None = None):
        self._by_scope = {
            "auth": MagicMock(
                from_env_var="ELAINE_TOKEN",
                auth_file=None,
                ci_env_variables=tuple(),
                token_expiration_threshold=30,
            ),
            "toolchain-setup": MagicMock(repo=repo, base_url="https://yoyoma.com"),
        }

    def for_global_scope(self):
        return MagicMock(pants_bin_name="pants")

    def for_scope(self, scope: str):
        return self._by_scope[scope]


def add_token_response(responses) -> None:
    responses.add(
        responses.POST,
        "https://yoyoma.com/api/v1/token/refresh/",
        json={
            "remote_cache": {"address": "grpcs://no.soup.for.jerry.com:443"},
            "token": {
                "access_token": "Oh Henry!",
                "expires_at": "2029-08-21T19:41:46+00:00",
                "repo_id": "velvet",
                "customer_id": "TheMikado",
            },
        },
    )


def create_options(repo: str | None = None):
    return FakeOptions(repo=repo)


def test_auth_plugin(responses) -> None:
    options = create_options("jerry")
    add_token_response(responses)
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING})
    assert result.is_available is True
    assert result.store_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.execution_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.instance_name == "TheMikado"
    assert len(responses.calls) == 1


def test_auth_plugin_http_error(responses) -> None:
    options = create_options("jerry")
    responses.add(responses.POST, "https://yoyoma.com/api/v1/token/refresh/", status=400)
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING})
    assert result.is_available is False
    assert not result.store_headers
    assert not result.execution_headers
    assert result.instance_name is None
    assert len(responses.calls) == 1


def test_auth_plugin_network_error(responses) -> None:
    options = create_options("jerry")
    responses.add(responses.POST, "https://yoyoma.com/api/v1/token/refresh/", body=SSLError("No Bagel"))
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING})
    assert result.is_available is False
    assert not result.store_headers
    assert not result.execution_headers
    assert result.instance_name is None
    assert len(responses.calls) == 1


def test_auth_plugin_no_repo():
    options = create_options()
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING})
    assert result.is_available is False


def test_warn_on_overwritten_headers(caplog, responses) -> None:
    options = create_options("jerry")
    add_token_response(responses)
    result = toolchain_auth_plugin(
        {"Authorization": "exec header", "sandwiches": "bologna"},
        {"Authorization": "store header", "hands": "soft and milky white"},
        options,
        env={"ELAINE_TOKEN": TEST_TOKEN_STRING},
    )
    assert len(responses.calls) == 1
    assert result.is_available is True
    assert result.store_headers == {"Authorization": "Bearer Oh Henry!", "hands": "soft and milky white"}
    assert result.execution_headers == {"Authorization": "Bearer Oh Henry!", "sandwiches": "bologna"}
    assert result.instance_name == "TheMikado"
    assert_messages(
        caplog,
        "The following remote execution header\\(s\\) will be overwritten by the Toolchain plugin: Authorization",
    )
    assert_messages(
        caplog, "The following remote store header\\(s\\) will be overwritten by the Toolchain plugin: Authorization"
    )


def test_with_expiration(responses) -> None:
    options = create_options("jerry")
    add_token_response(responses)
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING})
    assert result.is_available is True
    assert result.store_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.execution_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.instance_name == "TheMikado"
    assert result.expiration == datetime.datetime(2029, 8, 21, 19, 11, 46, tzinfo=datetime.timezone.utc)
    assert len(responses.calls) == 1


def test_with_prior_result_expired(responses) -> None:
    options = create_options("jerry")
    add_token_response(responses)
    prior_result = create_prior_result(
        state=AuthPluginState.OK,
        token="festivus-miracle",
        instance_name="frank",
        expiration=datetime.datetime(2021, 3, 20, tzinfo=datetime.timezone.utc),
    )
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING}, prior_result=prior_result)
    assert result.is_available is True
    assert result.store_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.execution_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.instance_name == "TheMikado"
    assert result.expiration == datetime.datetime(2029, 8, 21, 19, 11, 46, tzinfo=datetime.timezone.utc)
    assert len(responses.calls) == 1


def test_with_prior_result_valid() -> None:
    options = create_options("jerry")

    prior_result = create_prior_result(
        state=AuthPluginState.OK,
        token="aluminum-pole",
        instance_name="elaine-marie-benes",
        expiration=datetime.datetime(2025, 3, 20, tzinfo=datetime.timezone.utc),
    )
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING}, prior_result=prior_result)
    assert id(result) == id(prior_result)
    assert result.is_available is True
    assert result.store_headers == {"Authorization": "Bearer aluminum-pole"}
    assert result.execution_headers == {"Authorization": "Bearer aluminum-pole"}
    assert result.instance_name == "elaine-marie-benes"
    assert result.expiration == datetime.datetime(2025, 3, 20, tzinfo=datetime.timezone.utc)


def test_with_prior_result_disabled(responses) -> None:
    options = create_options("jerry")
    add_token_response(responses)
    prior_result = create_prior_result(
        state=AuthPluginState.UNAVAILABLE,
        token=None,
        instance_name="mandelbaum",
        expiration=None,
    )
    result = toolchain_auth_plugin({}, {}, options, env={"ELAINE_TOKEN": TEST_TOKEN_STRING}, prior_result=prior_result)
    assert result.is_available is True
    assert result.store_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.execution_headers == {"Authorization": "Bearer Oh Henry!"}
    assert result.instance_name == "TheMikado"
    assert result.expiration == datetime.datetime(2029, 8, 21, 19, 11, 46, tzinfo=datetime.timezone.utc)
    assert len(responses.calls) == 1
