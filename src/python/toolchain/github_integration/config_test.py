# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.util.config.app_config import AppConfig
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor, SecretNotFound, SecretsAccessor


class TestGithubIntegrationConfig:
    @pytest.fixture()
    def secrets_accessor(self) -> SecretsAccessor:
        DummySecretsAccessor._instance = None
        return DummySecretsAccessor.create_rotatable()

    def test_missing_secret(self, secrets_accessor: SecretsAccessor) -> None:
        app_cfg = AppConfig({"GITHUB_CONFIG": {"app_id": "777711", "public_link": "https://jerry.com/newman"}})
        with pytest.raises(SecretNotFound, match="Secret 'github-app-private-key' not found"):
            GithubIntegrationConfig.from_secrets_and_config(app_cfg, secrets_accessor)

    def test_config(self, secrets_accessor: SecretsAccessor) -> None:
        secrets_accessor.set_secret("github-app-private-key", "No soup for you")
        app_cfg = AppConfig({"GITHUB_CONFIG": {"app_id": "777711", "public_link": "https://jerry.com/newman"}})
        config = GithubIntegrationConfig.from_secrets_and_config(app_cfg, secrets_accessor)
        assert config.app_id == "777711"
        assert config.private_key == b"No soup for you"
        assert config.public_link == "https://jerry.com/newman/"

    def test_dont_leak_private_key(self, secrets_accessor: SecretsAccessor) -> None:
        secrets_accessor.set_secret("github-app-private-key", "No soup for you")
        app_cfg = AppConfig({"GITHUB_CONFIG": {"app_id": "777711", "public_link": "https://jerry.com/newman"}})
        config = GithubIntegrationConfig.from_secrets_and_config(app_cfg, secrets_accessor)
        assert "No soup for you" not in str(config)
        assert "No soup for you" not in repr(config)
