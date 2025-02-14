# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from typing import cast
from unittest import mock
from urllib.parse import parse_qsl, urlparse

import pytest
import requests
from jose import jwt
from pants.engine.fs import CreateDigest, Digest, Workspace
from pants.option.global_options import GlobalOptions
from pants.testutil.option_util import create_options_bootstrapper, create_subsystem
from pants.testutil.rule_runner import MockGet, QueryRule, RuleRunner, mock_console, run_rule_with_mocks

from toolchain.base.datetime_tools import utcnow
from toolchain.pants.auth.rules import (
    AccessTokenAcquisition,
    AccessTokenAcquisitionGoalOptions,
    AuthStoreOptions,
    AuthTokenCheckGoalOptions,
    AuthTokenInfo,
    AuthTokenInfoGoalOptions,
    OutputType,
    acquire_access_token,
    check_auth_token,
    show_token_info,
)
from toolchain.pants.auth.server import TestPage
from toolchain.pants.auth.store import AuthStore
from toolchain.pants.common.toolchain_setup import ToolchainSetup, ToolchainSetupError
from toolchain.util.constants import REQUEST_ID_HEADER


def fake_get_has_browser():
    return "jambalaya"


def fake_get_no_browser():
    raise webbrowser.Error("Browser N/A")


class TestAuthAcquireRule:
    _WAIT_TIMEOUT = 10  # seconds
    _POLL_INTERVAL = 0.1

    def _get_state(self, mock_wb) -> str:
        wait_until = time.time() + self._WAIT_TIMEOUT
        while wait_until > time.time():
            time.sleep(self._POLL_INTERVAL)
            if mock_wb.called:
                browser_url = mock_wb.call_args[0][0]
                return dict(parse_qsl(urlparse(browser_url).query))["state"]
        raise AssertionError("Failed to get state from mock web browser call")

    def _call_local_server(self, url: str, code: str, state: str) -> None:
        wait_until = time.time() + self._WAIT_TIMEOUT
        while wait_until > time.time():
            time.sleep(self._POLL_INTERVAL)
            try:
                requests.get(url, params={"code": code, "state": state}, timeout=2)
                return
            except requests.RequestException:
                pass
        raise AssertionError(f"Can't reach local web server at {url}")

    def _mock_browser_thread(self, url: str, code: str, mock_wb) -> None:
        try:
            state = self._get_state(mock_wb)
            self._call_local_server(url, code, state)
        except AssertionError as error:
            self._error = error

    @pytest.fixture()
    def org_name(self) -> str:
        return "festivus"

    def _run_acquire_rule(
        self,
        port: int,
        base_url: str,
        org_name: str,
        output: OutputType = OutputType.CONSOLE,
        description="freckles’ ugly cousin",
        remote_execution: bool = False,
    ) -> tuple[str, str, int, Path]:
        runner = RuleRunner(rules=[QueryRule(Digest, [CreateDigest])])
        with mock_console(create_options_bootstrapper()) as (console, stdio_reader):
            acquisition_options = create_subsystem(
                AccessTokenAcquisitionGoalOptions,
                local_port=port,
                output=output,
                headless=False,
                test_page=TestPage.NA,
                description=description,
                for_ci=output == OutputType.CONSOLE,
                remote_execution=remote_execution,
            )

            def mock_create_digest(fc):
                return runner.request(Digest, [fc])

            auth_store_options = create_subsystem(AuthStoreOptions, auth_file="newman/seinfeld/puddy.json")
            global_ops = create_subsystem(GlobalOptions, pants_bin_name="dingo")
            setup = create_subsystem(ToolchainSetup, repo="puddy", base_url=base_url, org=org_name)
            result: AccessTokenAcquisition = run_rule_with_mocks(
                acquire_access_token,
                rule_args=[
                    console,
                    Workspace(runner.scheduler, _enforce_effects=False),
                    acquisition_options,
                    auth_store_options,
                    global_ops,
                    setup,
                ],
                mock_gets=[
                    MockGet(output_type=Digest, input_types=(CreateDigest,), mock=mock_create_digest),
                ],
            )
            return stdio_reader.get_stdout(), stdio_reader.get_stderr(), result.exit_code, Path(runner.build_root)

    def _start_web_browser_thread(self, responses, local_port, code, mock_wb) -> None:
        url = f"http://localhost:{local_port}/token-callback/"
        responses.add_passthru(url)
        thread = Thread(target=self._mock_browser_thread, daemon=True, args=(url, code, mock_wb))
        thread.start()

    @mock.patch("webbrowser.open")
    @mock.patch("webbrowser.get", new=fake_get_has_browser)
    def test_acquire_access_token_console(self, mock_browser_open, responses, org_name: str) -> None:
        mock_browser_open.return_value = True
        local_port = 9911
        responses.add(
            responses.POST,
            "http://little.jerry.com/api/v1/token/exchange/",
            json={"access_token": "elaine-marie-benes", "expires_at": "2028-01-05T19:39:34.231185+00:00"},
        )
        self._start_web_browser_thread(responses, local_port, "novacine", mock_browser_open)
        stdout, stderr, exit_code, _ = self._run_acquire_rule(
            local_port, "http://little.jerry.com", org_name, OutputType.CONSOLE
        )
        assert exit_code == 0
        lines = stdout.split("\n")
        assert "Access Token is: elaine-marie-benes" in lines
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == "http://little.jerry.com/api/v1/token/exchange/"
        assert request.body == "code=novacine&desc=freckles%E2%80%99+ugly+cousin&allow_impersonation=1"

    @mock.patch("webbrowser.open")
    @mock.patch("webbrowser.get", new=fake_get_has_browser)
    def test_acquire_access_token_server_error(self, mock_browser_open, responses, org_name: str) -> None:
        mock_browser_open.return_value = True
        local_port = 9911
        responses.add(
            responses.POST,
            "http://little.jerry.com/api/v1/token/exchange/",
            status=403,
            json={"message": "no token for you, come back one year"},
            adding_headers={REQUEST_ID_HEADER: "soup"},
        )
        self._start_web_browser_thread(responses, local_port, "novacine", mock_browser_open)
        _, stderr, exit_code, _ = self._run_acquire_rule(9911, "http://little.jerry.com", org_name)
        lines = stderr.split("\n")
        assert "HTTP: 403: no token for you, come back one year request=soup" in lines

    @mock.patch("webbrowser.get", new=fake_get_no_browser)
    def test_acquire_access_token_headless(self, monkeypatch, responses, org_name: str) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "monks")
        responses.add(
            responses.POST,
            "http://little.jerry.com/api/v1/token/exchange/",
            json={"access_token": "feats-of-strength", "expires_at": "2028-01-05T19:39:34.231185+00:00"},
        )
        stdout, _, exit_code, _ = self._run_acquire_rule(9911, "http://little.jerry.com", org_name)
        assert exit_code == 0
        lines = stdout.split("\n")
        assert "Access Token is: feats-of-strength" in lines
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == "http://little.jerry.com/api/v1/token/exchange/"
        assert request.body == "code=monks&desc=freckles%E2%80%99+ugly+cousin&allow_impersonation=1"

    @mock.patch("webbrowser.get", new=fake_get_no_browser)
    def test_acquire_access_token_headless_to_file(self, monkeypatch, responses, org_name: str) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "monks")
        responses.add(
            responses.POST,
            "http://little.jerry.com/api/v1/token/exchange/",
            json={
                "access_token": "kruger",
                "expires_at": "2028-01-05T19:39:34.231185+00:00",
                "repo_id": "huston",
                "customer_id": "timer",
            },
        )
        stdout, _, exit_code, build_root = self._run_acquire_rule(
            9911, "http://little.jerry.com", org_name, output=OutputType.FILE
        )
        auth_file = build_root / "newman/seinfeld/puddy.json"
        assert auth_file.exists()
        assert json.loads(auth_file.read_bytes()) == {
            "access_token": "kruger",
            "expires_at": "2028-01-05T19:39:34.231185+00:00",
            "repo": None,
            "user": None,
            "repo_id": "huston",
            "customer_id": "timer",
        }
        assert exit_code == 0
        assert "Access token acquired and stored." in stdout.split("\n")
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == "http://little.jerry.com/api/v1/token/exchange/"
        assert request.body == "code=monks&desc=freckles%E2%80%99+ugly+cousin"

    @pytest.mark.skip(reason="Test times out, probably due to usage of input()")
    @mock.patch("webbrowser.open")
    @mock.patch("webbrowser.get", new=fake_get_has_browser)
    def test_acquire_access_token_custom_description(self, monkeypatch, responses, org_name: str) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "He stopped short")
        responses.add(
            responses.POST,
            "http://little.jerry.com/api/v1/token/exchange/",
            json={
                "access_token": "kruger",
                "expires_at": "2028-01-05T19:39:34.231185+00:00",
                "repo_id": "huston",
                "customer_id": "timer",
            },
        )
        stdout, _, exit_code, build_root = self._run_acquire_rule(
            9911,
            "http://little.jerry.com",
            org_name=org_name,
            output=OutputType.FILE,
            description="He stopped short",
        )
        auth_file = build_root / ".pants.d" / "toolchain_auth" / "auth_token.json"
        assert auth_file.exists()
        assert json.loads(auth_file.read_bytes()) == {
            "access_token": "kruger",
            "expires_at": "2028-01-05T19:39:34.231185+00:00",
            "repo": None,
            "user": None,
            "repo_id": "huston",
            "customer_id": "timer",
        }
        assert exit_code == 0
        assert "Access token acquired and stored." in stdout.split("\n")
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == "http://little.jerry.com/api/v1/token/exchange/"
        assert request.body == "code=monks&desc=XS"

    @mock.patch("webbrowser.get", new=fake_get_no_browser)
    def test_acquire_access_token_fail_no_org(self, monkeypatch, responses) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "monks")
        with pytest.raises(
            ToolchainSetupError,
            match=r'Please set org = "\<your org name\>" in the \[toolchain-setup\] section',
        ):
            self._run_acquire_rule(9911, "http://little.jerry.com", "", output=OutputType.FILE)

        assert len(responses.calls) == 0


def _create_auth_store(env: dict[str, str] | None = None, **store_options) -> AuthStore:
    auth_store_final_options = {
        "token_expiration_threshold": 21,
        "org": "costanza",
        "from_env_var": None,
        "auth_file": "jerry.json",
        "ci_env_variables": [],
        "restricted_token_matches": {},
    }
    auth_store_final_options.update(store_options)
    auth_store_options = cast(AuthStoreOptions, create_subsystem(AuthStoreOptions, **auth_store_final_options))  # type: ignore[arg-type]
    return AuthStore(
        context="rules-test",
        options=auth_store_options,
        pants_bin_name="jerry",
        env=env or {},
        repo="david",
        base_url="https:/puddy",
    )


def _encode_token(expires_at: datetime) -> str:
    issued_at = expires_at - timedelta(days=91)
    claims = {
        "exp": int(expires_at.timestamp()),
        "iat": int(issued_at.timestamp()),
        "jid": "chicken",
    }

    return jwt.encode(claims=claims, key="no-soup-for-you", algorithm="HS256")


def _prep_token_file(auth_file_path: Path, expires_at: datetime | None = None) -> None:
    token_expiration = expires_at or (utcnow() + timedelta(days=30))
    token = _encode_token(expires_at=token_expiration)
    auth_file_path.write_text(
        json.dumps(
            {
                "access_token": token,
                "expires_at": token_expiration.isoformat(),
                "user": "jerry",
                "repo": "bob",
                "repo_id": None,
                "customer_id": None,
            }
        )
    )


class TestShowTokenInfoRule:
    def _run_show_token_info_rule(self, verbose: bool, use_json: bool, auth_file_path: Path) -> tuple[str, str, int]:
        with mock_console(create_options_bootstrapper()) as (console, stdio_reader):
            token_info_options = create_subsystem(AuthTokenInfoGoalOptions, verbose=verbose, json=use_json)
            store = _create_auth_store(auth_file=auth_file_path.as_posix())
            result: AuthTokenInfo = run_rule_with_mocks(
                show_token_info,
                rule_args=[console, store, token_info_options],
            )
            return stdio_reader.get_stdout(), stdio_reader.get_stderr(), result.exit_code

    def test_show_token_info_basic(self, tmp_path: Path) -> None:
        auth_file_path = tmp_path / "puddy.json"
        _prep_token_file(auth_file_path, expires_at=datetime(2031, 12, 13, tzinfo=timezone.utc))
        stdout, _, exit_code = self._run_show_token_info_rule(
            verbose=False, use_json=False, auth_file_path=auth_file_path
        )
        assert exit_code == 0
        lines = stdout.split("\n")
        assert lines[0].startswith("token id: chicken expires at: 2031-12-13 00:00:00+00:00 (in ")

    def test_show_token_info_verbose(self, tmp_path: Path) -> None:
        auth_file_path = tmp_path / "puddy.json"
        _prep_token_file(auth_file_path, expires_at=datetime(2031, 12, 13, tzinfo=timezone.utc))
        stdout, _, exit_code = self._run_show_token_info_rule(
            verbose=True, use_json=False, auth_file_path=auth_file_path
        )
        assert exit_code == 0
        lines = stdout.split("\n")
        assert lines[0].startswith("token id: chicken expires at: 2031-12-13 00:00:00+00:00 (in ")
        assert "\n".join(lines[1:]) == "exp=1954886400\niat=1947024000\njid=chicken\n"

    def test_show_token_info_JSON(self, tmp_path: Path) -> None:
        auth_file_path = tmp_path / "puddy.json"
        _prep_token_file(auth_file_path, expires_at=datetime(2031, 12, 13, tzinfo=timezone.utc))
        stdout, _, exit_code = self._run_show_token_info_rule(
            verbose=False, use_json=True, auth_file_path=auth_file_path
        )
        assert exit_code == 0
        assert json.loads(stdout) == {"exp": 1954886400, "iat": 1947024000, "jid": "chicken"}


class TestAuthTokenCheckRule:
    def _run_check_rule(self, auth_file_path: Path) -> tuple[str, str, int]:
        with mock_console(create_options_bootstrapper()) as (console, stdio_reader):
            check_options = create_subsystem(AuthTokenCheckGoalOptions, threshold=22)
            store = _create_auth_store(auth_file=auth_file_path.as_posix())
            result: AuthTokenInfo = run_rule_with_mocks(
                check_auth_token,
                rule_args=[console, store, check_options],
            )
            return stdio_reader.get_stdout(), stdio_reader.get_stderr(), result.exit_code

    def test_check_doesnt_expire_soon(self, tmp_path: Path) -> None:
        auth_file_path = tmp_path / "puddy.json"
        _prep_token_file(auth_file_path, expires_at=datetime(2034, 1, 20, tzinfo=timezone.utc))
        *_, exit_code = self._run_check_rule(auth_file_path)
        assert exit_code == 0

    def test_check_already_expired(self, tmp_path: Path) -> None:
        auth_file_path = tmp_path / "puddy.json"
        _prep_token_file(auth_file_path, expires_at=datetime(2021, 12, 31, tzinfo=timezone.utc))
        _, stderr, exit_code = self._run_check_rule(auth_file_path)
        assert exit_code == -1
        assert stderr == "Token expired at 2021-12-31T00:00:00+00:00\n"

    def test_check_expires_soon(self, tmp_path: Path) -> None:
        auth_file_path = tmp_path / "puddy.json"
        _prep_token_file(auth_file_path, expires_at=utcnow() - timedelta(days=9))
        _, stderr, exit_code = self._run_check_rule(auth_file_path)
        assert exit_code == -1
        assert stderr.startswith("Token expired at 202")
