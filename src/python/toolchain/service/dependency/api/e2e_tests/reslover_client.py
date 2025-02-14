# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from dateutil.parser import parse

from toolchain.base.datetime_tools import utcnow


@dataclass(frozen=True)
class AuthToken:
    access_token: str
    expires_at: datetime.datetime


class ResolveClient:
    _PROD_TOKEN_FILE = Path(".pants.d/toolchain_auth/auth_token.json")
    _DEV_TOKEN_FILE = Path(".pants.d/toolchain_auth/auth-dev.json")
    _PROD_URL_BASE = "https://app.toolchain.com"
    _DEV_URL_BASE = "http://localhost:9500"

    def __init__(self, is_dev: bool) -> None:
        # Super hacky init, only works on asher's machine. needs to be more robust.
        if is_dev:
            token_file = self._DEV_TOKEN_FILE
            self._url_base = self._DEV_URL_BASE
        else:
            token_file = self._PROD_TOKEN_FILE
            self._url_base = self._PROD_URL_BASE
        self._refresh_token = json.loads(token_file.read_bytes())["access_token"]
        self._access_token = self._acquire_token()

    @property
    def _now(self):
        return utcnow().replace(tzinfo=datetime.timezone.utc)

    def _acquire_token(self):
        headers = {"Authorization": f"Bearer {self._refresh_token}", "User-Agent": "resolver-e2e-tests"}
        response = requests.post(f"{self._url_base}/api/v1/token/refresh/", headers=headers)
        response.raise_for_status()
        resp_json = response.json()
        return AuthToken(access_token=resp_json["access_token"], expires_at=parse(resp_json["expires_at"]))

    def _get_access_token(self) -> str:
        expiration_threshold = self._now + datetime.timedelta(seconds=30)
        if self._access_token.expires_at < expiration_threshold:
            self._access_token = self._acquire_token()
        return self._access_token.access_token

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_access_token()}", "User-Agent": "resolver-e2e-tests"}

    def resolve(self, *, requirement_strings: list[str], python: str, platform: str) -> tuple[bool, dict]:
        data = dict(dependencies=requirement_strings, py=python, platform=platform)
        resolve_url = f"{self._url_base}/api/v1/packagerepo/pypi/resolve/"
        response = requests.post(url=resolve_url, headers=self._get_headers(), json=data)
        self._handle_response(resolve_url, data, response)

        json_resp = response.json()
        resolve_run = "solution" in json_resp
        if not resolve_run:
            return False, json_resp

        solution_id = json_resp["solution"]["id"]
        url = f"{resolve_url}{solution_id}/"
        time.sleep(8)  # Initial wait
        timeout_time = time.time() + 80
        while time.time() < timeout_time:
            time.sleep(2)
            response = requests.get(url, headers=self._get_headers())
            self._handle_response(url, data, response)
            resp_json = response.json()
            if "solution" not in resp_json:
                return True, resp_json
        raise AssertionError(f"Resolve requirements timed out: {url}")

    def _handle_response(self, url, data, response):
        if response.status_code == 400:
            data_txt = json.dumps(data, indent=4)
            raise AssertionError(f"FAILED: {data_txt} -- {response.text}")
        if not response.ok:
            raise AssertionError(f"Resolve failed {url} -- {response.text}")
