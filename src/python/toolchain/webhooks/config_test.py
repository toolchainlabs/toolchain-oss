# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest

from toolchain.util.secret.secrets_accessor import DummySecretsAccessor, SecretNotFound, SecretsAccessor
from toolchain.webhooks.config import WebhookConfiguration


class TestWebhookConfiguration:
    @pytest.fixture()
    def secrets_accessor(self) -> SecretsAccessor:
        DummySecretsAccessor._instance = None
        return DummySecretsAccessor.create_rotatable()

    def test_load_from_secret(self, secrets_accessor) -> None:
        secrets_accessor.set_secret("github-app-webhook-secret", "pimple-popper-md")
        cfg = WebhookConfiguration.from_secrets(secrets_accessor)
        assert cfg.github_webhook_secrets == (b"pimple-popper-md",)

    def test_missing_secret(self, secrets_accessor) -> None:
        with pytest.raises(SecretNotFound, match="Secret 'github-app-webhook-secret' not found"):
            WebhookConfiguration.from_secrets(secrets_accessor)

    def test_load_from_secret_new(self, secrets_accessor) -> None:
        secrets_accessor.set_secret("github-app-webhook-secret", "pimple-popper-md")
        secrets_accessor.set_secret(
            "github-app-webhook-secrets", json.dumps(["you-lost-a-lot-of-hair", "fiber-from-shirt"])
        )
        cfg = WebhookConfiguration.from_secrets(secrets_accessor)
        assert cfg.github_webhook_secrets == (b"you-lost-a-lot-of-hair", b"fiber-from-shirt")
