# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from pathlib import Path

from pants.testutil.option_util import create_subsystem

from toolchain.pants.auth.client import AuthState
from toolchain.pants.auth.rules import AuthStoreOptions
from toolchain.pants.auth.store import AuthStore


class TestAutStore:
    def _get_store(self, responses, tmp_path: Path) -> AuthStore:
        token_file = tmp_path / "fake_token.json"
        token_file.write_text(
            json.dumps({"access_token": "pez-dispenser", "expires_at": "2029-01-12T10:00:00+00:00"}), encoding="utf-8"
        )
        auth_store_options = create_subsystem(
            AuthStoreOptions,
            auth_file=str(token_file),
            org=None,
            from_env_var=None,
            ci_env_variables=tuple(),  # type: ignore[arg-type]
            restricted_token_matches=dict(),
            token_expiration_threshold=30,
        ).options
        return AuthStore(
            context="test",
            options=auth_store_options,
            pants_bin_name="jerry",
            env={},
            repo=None,
            base_url="http://festivus.com",
        )

    def _add_token_response(
        self, responses, expiration: datetime.datetime | None = None, token: str = "double-dip"
    ) -> None:
        expiration = expiration or datetime.datetime(2027, 8, 21, 19, 41, 46, tzinfo=datetime.timezone.utc)
        responses.add(
            responses.POST,
            "http://festivus.com/api/v1/token/refresh/",
            json={
                "remote_cache": {"address": "grpcs://no.soup.for.jerry.com:443"},
                "token": {"access_token": token, "expires_at": expiration.isoformat()},
            },
        )

    def _add_token_response_fail(self, responses) -> None:
        responses.add(responses.POST, "http://festivus.com/api/v1/token/refresh/", status=403, json={"rejected": True})

    def test_get_access_token(self, responses, tmp_path: Path) -> None:
        self._add_token_response(responses)
        store = self._get_store(responses, tmp_path)
        token = store.get_access_token()
        assert len(responses.calls) == 1
        assert token.access_token == "double-dip"
        assert token.expires_at == datetime.datetime(2027, 8, 21, 19, 41, 46, tzinfo=datetime.timezone.utc)
        token_2 = store.get_access_token()
        assert token_2 == token
        assert len(responses.calls) == 1

    def test_get_auth_state(self, responses, tmp_path: Path) -> None:
        self._add_token_response(responses)
        store = self._get_store(responses, tmp_path)
        assert len(responses.calls) == 0
        assert store.get_auth_state() == AuthState.OK
        assert len(responses.calls) == 1

    def test_get_auth_state_fail(self, responses, tmp_path: Path) -> None:
        self._add_token_response_fail(responses)
        store = self._get_store(responses, tmp_path)
        assert len(responses.calls) == 0
        assert store.get_auth_state() == AuthState.FAILED
        assert len(responses.calls) == 1
        assert store.get_auth_state() == AuthState.FAILED
        assert len(responses.calls) == 1

    def test_get_auth_state_transient_and_success(self, responses, tmp_path: Path) -> None:
        responses.add(responses.POST, "http://festivus.com/api/v1/token/refresh/", status=503)
        self._add_token_response(responses)
        store = self._get_store(responses, tmp_path)
        assert len(responses.calls) == 0
        assert store.get_auth_state() == AuthState.TRANSIENT_FAILURE
        assert len(responses.calls) == 1
        assert store.get_auth_state() == AuthState.OK
        assert len(responses.calls) == 2

    def test_get_token_after_expiration(self, responses, tmp_path: Path) -> None:
        self._add_token_response(responses, datetime.datetime(2020, 12, 1, tzinfo=datetime.timezone.utc), token="pez")
        self._add_token_response(responses)
        store = self._get_store(responses, tmp_path)
        assert len(responses.calls) == 0
        token = store.get_access_token()
        assert len(responses.calls) == 1
        assert token.access_token == "pez"
        assert token.has_token is True
        assert token.has_expired() is True
        token = store.get_access_token()
        assert len(responses.calls) == 2
        assert token.access_token == "double-dip"
        assert token.has_token is True
        assert token.has_expired() is False
