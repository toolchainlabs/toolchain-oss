#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterator

import httpx
import pytest

from toolchain.constants import ToolchainEnv
from toolchain.github_integration.test_utils.fixtures_loader import load_fixture
from toolchain.prod.e2e_tests.helpers import wait_for_host
from toolchain.prod.e2e_tests.pytest_runner import run_pytest
from toolchain.util.secret.secrets_accessor_factories import get_secrets_reader
from toolchain.webhooks.config import WebhookConfiguration


def load_bytes_fixture(fixture_name: str) -> bytes:
    return json.dumps(load_fixture(fixture_name)).encode()


@pytest.fixture(scope="module")
def github_app_webhook_secret(tc_env: ToolchainEnv) -> bytes:
    reader = get_secrets_reader(toolchain_env=tc_env, is_k8s=True, use_remote_dbs=False, k8s_namespace=tc_env.namespace)  # type: ignore[attr-defined]
    # reader = get_secrets_reader(toolchain_env=tc_env, is_k8s=False, use_remote_dbs=True, k8s_namespace=tc_env.namespace)  # type: ignore[attr-defined]
    cfg = WebhookConfiguration.from_secrets(reader)
    return cfg.github_webhook_secrets[0]


@pytest.fixture(scope="module")
def http_client(host: str, tc_env: ToolchainEnv) -> Iterator[httpx.Client]:
    if tc_env.is_prod:  # type: ignore[attr-defined]
        # In prod (mostly staging) we need to wait for the ALB to be provisioned and for the DNS to be updated
        # This can take a few minutes.
        wait_for_host(host)
    scheme = "http" if tc_env.is_dev else "https"  # type: ignore[attr-defined]
    with httpx.Client(base_url=f"{scheme}://{host}/", headers={"User-Agent": "end2end-test-client"}) as client:
        yield client


def test_robots_txt(http_client: httpx.Client) -> None:
    resp = http_client.get("robots.txt")
    resp.raise_for_status()
    assert resp.status_code == 200
    assert resp.text == "User-agent: *\nDisallow: /"


def test_github_app(http_client: httpx.Client, github_app_webhook_secret: bytes) -> None:
    payload = load_bytes_fixture("ping")
    digest = hmac.new(github_app_webhook_secret, payload, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "internal-tc-test",
        "X-Hub-Signature-256": f"sha256={digest}",
    }
    resp = http_client.post("github/app/", content=payload, headers=headers)
    resp.raise_for_status()
    assert resp.status_code == 200
    assert resp.content == b"OK"


def test_bitbucket_app_descriptor(http_client: httpx.Client) -> None:
    resp = http_client.get("bitbucket/descriptor/")
    resp.raise_for_status()
    assert resp.status_code == 200
    assert resp.json()["vendor"]["name"] == "Toolchain Labs"


if __name__ == "__main__":
    run_pytest(__file__)
