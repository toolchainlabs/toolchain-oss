# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from contextlib import contextmanager
from functools import wraps
from unittest import mock

import pytest
from moto import mock_secretsmanager

from toolchain.aws.test_utils.secrets import create_fake_secret
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.ensure_secrets import EnsureSecrets
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor


@contextmanager
def get_k8s_secrets_accessor_mocks():
    def create_fake_k8s_rotatable_secrets_accessor(*args, **kwargs):
        return DummySecretsAccessor.create_rotatable()

    def create_fake_k8s_secrets_accessor(*args, **kwargs):
        return DummySecretsAccessor.create_rotatable()

    k8s_mocks = [
        mock.patch(
            "toolchain.prod.ensure_secrets.KubernetesSecretsAccessor.create_rotatable",
            new=create_fake_k8s_rotatable_secrets_accessor,
        ),
        mock.patch(
            "toolchain.prod.ensure_secrets.KubernetesSecretsAccessor.create", new=create_fake_k8s_secrets_accessor
        ),
    ]
    DummySecretsAccessor._instance = None
    try:
        for k8s_mock in k8s_mocks:
            k8s_mock.start()
        yield
    finally:
        for k8s_mock in k8s_mocks:
            k8s_mock.stop()


def mock_k8s_secrets_accessor():
    def decorator_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            with get_k8s_secrets_accessor_mocks():
                return func(*args, **kwds)

        return wrapper

    return decorator_wrapper


class TestEnsureSecrets:
    _FAKE_REGION = "ap-northeast-1"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_secretsmanager():
            yield

    def _create_tool(self, secret: str) -> EnsureSecrets:
        return EnsureSecrets.create_for_args(
            cluster=KubernetesCluster.PROD,
            aws_region=self._FAKE_REGION,
            dry_run=False,
            overwrite=False,
            secrets=[secret],
        )

    @mock_k8s_secrets_accessor()
    def test_github_app_webhook_secrets_no_existing_secret(self) -> None:
        create_fake_secret(
            region=self._FAKE_REGION,
            name="github-prod-app-creds",
            secret={"GITHUB_APP_WEBHOOK_SECRET": "a-case-of-kaiser-roles"},
        )
        tool = self._create_tool("github-app-webhook-secrets")
        assert tool.run() == 0
        secret_accessor = DummySecretsAccessor.create_rotatable()
        assert secret_accessor.get_json_secret_or_raise("github-app-webhook-secrets") == ["a-case-of-kaiser-roles"]

    @mock_k8s_secrets_accessor()
    def test_github_app_webhook_secrets_existing_secret(self) -> None:
        create_fake_secret(
            region=self._FAKE_REGION,
            name="github-prod-app-creds",
            secret={"GITHUB_APP_WEBHOOK_SECRET": "hallway-smells-like-potatoes"},
        )
        secret_accessor = DummySecretsAccessor.create_rotatable()
        secret_accessor.set_secret("github-app-webhook-secrets", json.dumps(["freckles-ugly-cousin"]))
        tool = self._create_tool("github-app-webhook-secrets")
        assert tool.run() == 0

        assert secret_accessor.get_json_secret_or_raise("github-app-webhook-secrets") == [
            "freckles-ugly-cousin",
            "hallway-smells-like-potatoes",
        ]
