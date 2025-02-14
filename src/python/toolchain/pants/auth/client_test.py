# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from freezegun import freeze_time
from requests.exceptions import ConnectionError

from toolchain.pants.auth.client import AuthClient, AuthError, AuthState
from toolchain.pants.auth.token import AuthToken
from toolchain.util.constants import REQUEST_ID_HEADER

TEST_TOKEN_STRING = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1OTAxNzk1ODgiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE1OTk2ODAzMzgsImlzcyI6InRvb2xjaGFpbiIsImlhdCI6MTU5OTY3OTczOCwiYXVkIjpbImJ1aWxkc2Vuc2UiLCJkZXBlbmRlbmN5IiwiaW1wZXJzb25hdGUiXSwidXNlcm5hbWUiOiJhc2hlciIsInR5cGUiOiJhY2Nlc3MiLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MiwidG9vbGNoYWluX3VzZXIiOiJmUTZBTnF1MnM5R3dBdkhDSnpqY2dBIiwidG9vbGNoYWluX3JlcG8iOiJLWExzU1hlOVpNVHlHMmRjV3ZyTHFuIiwidG9vbGNoYWluX2N1c3RvbWVyIjoiaGR0MmhuaVVYZW1zYUhEdWlCYXA0QiJ9.urUjGZCtAApqVgBA3Pa0hElHwAdZBEW6Iw8ZjmEgkyw"


class TestAuthClient:
    def _add_token_response(self, responses, extra_dicts: dict | None = None, **extra_fields) -> None:
        token_json = {
            "access_token": "Oh Henry!",
            "expires_at": "2029-08-21T19:41:46+00:00",
            **extra_fields,
        }

        responses.add(
            responses.POST,
            "http://festivus.com/api/v1/token/refresh/",
            json={
                "token": token_json,
                "remote_cache": {"address": "grpcs://no.soup.for.jerry.com:443"},
                **(extra_dicts or {}),
            },
        )

    def _add_restricted_token_response(self, responses) -> None:
        responses.add(
            responses.POST,
            "http://festivus.com/api/v1/token/restricted/",
            json={
                "token": {"access_token": "Oh Henry!", "expires_at": "2020-08-21T19:41:46+00:00"},
                "remote_cache": {"address": "grpcs://no.soup.for.jerry.com:443"},
            },
        )

    def _save_token_file(self, tmp_path) -> str:
        fn = tmp_path / "fake_token.json"
        token_dict = {"access_token": "Candy-bar fortune", "expires_at": "2030-03-21T03:19:12+00:00"}
        fn.write_text(json.dumps(token_dict), encoding="utf8")
        return str(fn)

    def _assert_token(self, token: AuthToken) -> None:
        assert token.has_token is True
        assert token.has_expired() is False
        assert token.expires_at == datetime.datetime(2029, 8, 21, 19, 41, 46, tzinfo=datetime.timezone.utc)
        assert token.access_token == "Oh Henry!"

    def test_with_file(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        self._add_token_response(responses, customer_id="alarm-clock", repo_id="captain")
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        token_and_cfg = options.acquire_access_token({})
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == "http://festivus.com/api/v1/token/refresh/"
        assert req.headers["Authorization"] == "Bearer Candy-bar fortune"
        assert req.body is None
        self._assert_token(token_and_cfg.auth_token)

    def test_with_file_extra_keys(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        self._add_token_response(responses, crossword="Captain-and-Tennille", repo_id="captain")
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        token_and_cfg = options.acquire_access_token({})
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == "http://festivus.com/api/v1/token/refresh/"
        assert req.headers["Authorization"] == "Bearer Candy-bar fortune"
        assert req.body is None
        self._assert_token(token_and_cfg.auth_token)

    @freeze_time(datetime.datetime(2020, 7, 9, tzinfo=datetime.timezone.utc))
    def test_with_env_var(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        self._add_token_response(responses)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
            env_var="SUE_ALLEN_TOKEN",
            ci_env_vars=tuple(),
        )
        token_and_cfg = options.acquire_access_token({"SUE_ALLEN_TOKEN": TEST_TOKEN_STRING})
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == "http://festivus.com/api/v1/token/refresh/"
        assert req.headers["Authorization"] == f"Bearer {TEST_TOKEN_STRING}"
        assert req.body is None
        self._assert_token(token_and_cfg.auth_token)

    @freeze_time(datetime.datetime(2020, 9, 4, tzinfo=datetime.timezone.utc))
    def test_with_env_var_expires_soon(self, responses, tmp_path: Path, caplog) -> None:
        fn = self._save_token_file(tmp_path)
        self._add_token_response(responses)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
            env_var="SUE_ALLEN_TOKEN",
            ci_env_vars=tuple(),
        )
        token_and_cfg = options.acquire_access_token({"SUE_ALLEN_TOKEN": TEST_TOKEN_STRING})
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == "http://festivus.com/api/v1/token/refresh/"
        assert req.headers["Authorization"] == f"Bearer {TEST_TOKEN_STRING}"
        assert req.body is None
        self._assert_token(token_and_cfg.auth_token)
        record = caplog.records[-1]
        assert (
            record.message == "Access token will expire in 5 days. - Run `newman auth-acquire` to acquire a new token."
        )
        assert record.levelname == "WARNING"

    def test_with_env_var_expired_token(self, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
            env_var="SUE_ALLEN_TOKEN",
            ci_env_vars=tuple(),
        )
        with pytest.raises(AuthError, match="Access token has expired") as excinfo:
            options.acquire_access_token({"SUE_ALLEN_TOKEN": TEST_TOKEN_STRING})
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    @freeze_time(datetime.datetime(2020, 7, 9, tzinfo=datetime.timezone.utc))
    def test_with_env_variables(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        self._add_token_response(responses)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
            env_var="SUE_ALLEN_TOKEN",
            ci_env_vars=("CHEW", "FLAVOR"),
        )
        token_and_cfg = options.acquire_access_token(
            {
                "SUE_ALLEN_TOKEN": TEST_TOKEN_STRING,
                "CHEW": "gum",
                "FLAVOR": "lo-mein-y",
            }
        )
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == "http://festivus.com/api/v1/token/refresh/"
        assert req.headers["Authorization"] == f"Bearer {TEST_TOKEN_STRING}"
        assert req.body is None
        self._assert_token(token_and_cfg.auth_token)

    def test_with_file_missing(self) -> None:
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="jerry.json",
        )
        with pytest.raises(AuthError, match="Failed to load auth token.*no default file or environment") as excinfo:
            options.acquire_access_token({})
        assert excinfo.value.get_state() == AuthState.UNAVAILABLE

    def test_with_invalid_env_var(self, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
            env_var="SUE_ALLEN_TOKEN",
        )
        with pytest.raises(AuthError, match="Access token not set in environment variable") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    def test_with_repo_and_no_env_vars(self) -> None:
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="kramer.json",
            env_var="SUE_ALLEN_TOKEN",
            repo_slug="kenny/bania",
        )
        with pytest.raises(
            AuthError,
            match="Access token not set in environment variable: SUE_ALLEN_TOKEN. customer_slug & ci_env_vars must be defined in order to acquire restricted access token",
        ) as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    def test_acquire_restricted(self, responses) -> None:
        self._add_restricted_token_response(responses)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="kramer.json",
            env_var="SUE_ALLEN_TOKEN",
            repo_slug="kenny/bania",
            ci_env_vars=("JERK_STORE", "MILOS"),
        )

        token_and_cfg = options.acquire_access_token(
            {
                "JERK_STORE": "is the line",
                "MILOS": "tennis",
            }
        )
        assert token_and_cfg.auth_token.access_token == "Oh Henry!"
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == "http://festivus.com/api/v1/token/restricted/"
        assert json.loads(request.body) == {
            "repo_slug": "kenny/bania",
            "env": {"JERK_STORE": "is the line", "MILOS": "tennis"},
        }

    def test_acquire_restricted_no_env_variables(self) -> None:
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="kramer.json",
            env_var="SUE_ALLEN_TOKEN",
            repo_slug="kenny/bania",
            ci_env_vars=("JERK_STORE", "MILOS"),
        )
        with pytest.raises(
            AuthError, match="Can't acquire restricted access token without environment variables"
        ) as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    def test_with_empty_env_var(self, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
            env_var="JERRY_TOKEN",
        )
        with pytest.raises(
            AuthError,
            match="Access token not set in environment variable: JERRY_TOKEN. customer_slug & ci_env_vars must be defined in order to acquire restricted access token.",
        ) as excinfo:
            options.acquire_access_token({"SUE_ALLEN_TOKEN": ""})
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    def test_with_invalid_file(self, tmp_path: Path) -> None:
        fn = tmp_path / "fake_token.json"
        fn.write_text("no soup for you", encoding="utf-8")
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=str(fn),
        )
        with pytest.raises(AuthError, match="Failed to load auth token: JSONDecodeError") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    def test_server_reject_token(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        responses.add(responses.POST, "http://festivus.com/api/v1/token/refresh/", status=403, json={"rejected": True})
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        with pytest.raises(AuthError, match="Auth rejected by server") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.FAILED
        assert state.is_final is True
        assert len(responses.calls) == 1

    def test_server_temporary_error(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        responses.add(responses.POST, "http://festivus.com/api/v1/token/refresh/", status=503)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        with pytest.raises(AuthError, match="transient server error") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.TRANSIENT_FAILURE
        assert state.is_final is False
        assert len(responses.calls) == 1

    def test_server_error(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        responses.add(responses.POST, "http://festivus.com/api/v1/token/refresh/", status=500)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        with pytest.raises(AuthError, match="Auth failed, unknown error") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.TRANSIENT_FAILURE
        assert state.is_final is False
        assert len(responses.calls) == 1

    def test_server_bad_request(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        responses.add(
            responses.POST,
            "http://festivus.com/api/v1/token/refresh/",
            status=400,
            json={"errors": "no soup for you"},
            adding_headers={REQUEST_ID_HEADER: "chicken"},
        )
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        with pytest.raises(AuthError, match="API Errors: no soup for you request_id=chicken") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.FAILED
        assert state.is_final is True
        assert len(responses.calls) == 1

    def test_network_error(self, responses, tmp_path: Path) -> None:
        fn = self._save_token_file(tmp_path)
        responses.add(
            responses.POST, "http://festivus.com/api/v1/token/refresh/", body=ConnectionError("Failed to connect")
        )
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        with pytest.raises(AuthError, match="Failed to connect") as excinfo:
            options.acquire_access_token({})
        state = excinfo.value.get_state()
        assert state == AuthState.TRANSIENT_FAILURE
        assert state.is_final is False
        assert len(responses.calls) == 1

    def test_restricted_token_with_matched_expression_not_matched(self) -> None:
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="kramer.json",
            env_var="SUE_ALLEN_TOKEN",
            repo_slug="kenny/bania",
            ci_env_vars=("JERK_STORE", "MILOS"),
            restricted_token_matches={"REPO_NAME": "jerry/festivus"},
        )
        env = {"JERK_STORE": "is the line", "MILOS": "tennis", "REPO": "cosmo/festivus"}
        with pytest.raises(
            AuthError, match="Restricted token expression didn't match, disabling Toolchain auth."
        ) as excinfo:
            options.acquire_access_token(env)
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    def test_restricted_token_with_matched_expression_missing_value(self) -> None:
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="kramer.json",
            env_var="SUE_ALLEN_TOKEN",
            repo_slug="kenny/bania",
            ci_env_vars=("JERK_STORE", "MILOS"),
            restricted_token_matches={"REPO_NAME": "jerry/festivus"},
        )
        env = {
            "JERK_STORE": "is the line",
            "MILOS": "tennis",
        }
        with pytest.raises(
            AuthError, match="Restricted token expression didn't match, disabling Toolchain auth."
        ) as excinfo:
            options.acquire_access_token(env)
        state = excinfo.value.get_state()
        assert state == AuthState.UNAVAILABLE
        assert state.is_final is True

    @pytest.mark.parametrize("repo_name", ["jerry/festivus", "jerry/festivus-miracle"])
    def test_restricted_token_with_matched_expression_success(self, responses, repo_name: str) -> None:
        self._add_restricted_token_response(responses)
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file="kramer.json",
            env_var="SUE_ALLEN_TOKEN",
            repo_slug="kenny/bania",
            ci_env_vars=("JERK_STORE", "MILOS"),
            restricted_token_matches={"REPO_NAME": "jerry/festiv.*"},
        )

        token_and_cfg = options.acquire_access_token(
            {"JERK_STORE": "is the line", "MILOS": "tennis", "REPO_NAME": repo_name}
        )
        assert token_and_cfg.auth_token.access_token == "Oh Henry!"
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == "http://festivus.com/api/v1/token/restricted/"
        assert json.loads(request.body) == {
            "repo_slug": "kenny/bania",
            "env": {"JERK_STORE": "is the line", "MILOS": "tennis"},
        }

    def test_with_server_messages(self, responses, tmp_path: Path, caplog) -> None:
        fn = self._save_token_file(tmp_path)
        self._add_token_response(
            responses,
            customer_id="alarm-clock",
            repo_id="captain",
            extra_dicts={"messages": [{"level": "WARNING", "msg": "I was in a pool"}]},
        )
        options = AuthClient.create(
            pants_bin_name="newman",
            base_url="http://festivus.com/api/v1",
            auth_file=fn,
        )
        token_and_cfg = options.acquire_access_token({})
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == "http://festivus.com/api/v1/token/refresh/"
        assert req.headers["Authorization"] == "Bearer Candy-bar fortune"
        assert req.body is None
        self._assert_token(token_and_cfg.auth_token)
        warn_msgs = [record.message for record in caplog.records if record.levelname == "WARNING"]
        assert warn_msgs == ["I was in a pool"]


class TestAuthToken:
    def test_from_json_dict(self) -> None:
        token = AuthToken.from_json_dict({"access_token": "Oh Henry!", "expires_at": "2020-08-21T19:41:46+00:00"})
        assert token.access_token == "Oh Henry!"
        assert token.expires_at == datetime.datetime(2020, 8, 21, 19, 41, 46, tzinfo=datetime.timezone.utc)
        assert token.user is None
        assert token.repo is None
        assert token.repo_id is None
        assert token.customer_id is None
        assert token.has_token is True

    def test_from_json_dict_with_ids(self) -> None:
        token = AuthToken.from_json_dict(
            {
                "access_token": "Oh Henry!",
                "expires_at": "2020-08-21T19:41:46+00:00",
                "customer_id": "hot-tub",
                "repo_id": "its-tollerable",
            }
        )
        assert token.access_token == "Oh Henry!"
        assert token.expires_at == datetime.datetime(2020, 8, 21, 19, 41, 46, tzinfo=datetime.timezone.utc)
        assert token.user is None
        assert token.repo is None
        assert token.repo_id == "its-tollerable"
        assert token.customer_id == "hot-tub"

        assert token.has_token is True

    def test_from_json_dict_with_unknown_keys(self) -> None:
        token = AuthToken.from_json_dict(
            {
                "access_token": "Oh Henry!",
                "expires_at": "2020-08-21T19:41:46+00:00",
                "catalog": "writer-block",
                "snooze": "knob",
            }
        )
        assert token.access_token == "Oh Henry!"
        assert token.expires_at == datetime.datetime(2020, 8, 21, 19, 41, 46, tzinfo=datetime.timezone.utc)
        assert token.user is None
        assert token.repo is None
        assert token.repo_id is None
        assert token.customer_id is None

        assert token.has_token is True

    def test_from_access_token_string(self) -> None:
        token = AuthToken.from_access_token_string(TEST_TOKEN_STRING)
        assert (
            token.access_token
            == "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1OTAxNzk1ODgiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE1OTk2ODAzMzgsImlzcyI6InRvb2xjaGFpbiIsImlhdCI6MTU5OTY3OTczOCwiYXVkIjpbImJ1aWxkc2Vuc2UiLCJkZXBlbmRlbmN5IiwiaW1wZXJzb25hdGUiXSwidXNlcm5hbWUiOiJhc2hlciIsInR5cGUiOiJhY2Nlc3MiLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MiwidG9vbGNoYWluX3VzZXIiOiJmUTZBTnF1MnM5R3dBdkhDSnpqY2dBIiwidG9vbGNoYWluX3JlcG8iOiJLWExzU1hlOVpNVHlHMmRjV3ZyTHFuIiwidG9vbGNoYWluX2N1c3RvbWVyIjoiaGR0MmhuaVVYZW1zYUhEdWlCYXA0QiJ9.urUjGZCtAApqVgBA3Pa0hElHwAdZBEW6Iw8ZjmEgkyw"
        )
        assert token.expires_at == datetime.datetime(2020, 9, 9, 19, 38, 58, tzinfo=datetime.timezone.utc)
        assert token.user == "fQ6ANqu2s9GwAvHCJzjcgA"
        assert token.repo == "KXLsSXe9ZMTyG2dcWvrLqn"
        assert token.has_token is True
        assert json.loads(token.to_json_string()) == {
            "access_token": "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1OTAxNzk1ODgiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE1OTk2ODAzMzgsImlzcyI6InRvb2xjaGFpbiIsImlhdCI6MTU5OTY3OTczOCwiYXVkIjpbImJ1aWxkc2Vuc2UiLCJkZXBlbmRlbmN5IiwiaW1wZXJzb25hdGUiXSwidXNlcm5hbWUiOiJhc2hlciIsInR5cGUiOiJhY2Nlc3MiLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MiwidG9vbGNoYWluX3VzZXIiOiJmUTZBTnF1MnM5R3dBdkhDSnpqY2dBIiwidG9vbGNoYWluX3JlcG8iOiJLWExzU1hlOVpNVHlHMmRjV3ZyTHFuIiwidG9vbGNoYWluX2N1c3RvbWVyIjoiaGR0MmhuaVVYZW1zYUhEdWlCYXA0QiJ9.urUjGZCtAApqVgBA3Pa0hElHwAdZBEW6Iw8ZjmEgkyw",
            "expires_at": "2020-09-09T19:38:58+00:00",
            "user": "fQ6ANqu2s9GwAvHCJzjcgA",
            "repo": "KXLsSXe9ZMTyG2dcWvrLqn",
            "repo_id": None,
            "customer_id": None,
        }

    def test_get_headers(self) -> None:
        token = AuthToken.from_json_dict({"access_token": "festivus", "expires_at": "2020-08-21T19:41:46+00:00"})
        assert token.get_headers() == {"Authorization": "Bearer festivus"}
