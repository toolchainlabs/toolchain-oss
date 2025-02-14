# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
import stripe

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.payments.stripe_integration.stripe_init import init_stripe
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor, SecretNotFound, SecretsAccessor


@pytest.fixture()
def secrets_accessor() -> SecretsAccessor:
    secrets_accessor = DummySecretsAccessor.get_instance()
    secrets_accessor.secrets.clear()
    return secrets_accessor


def test_init_stripe_invalid(secrets_accessor: SecretsAccessor) -> None:
    secrets_accessor.set_secret("stripe-integration", json.dumps({"api-key": "jambalaya"}))
    with pytest.raises(ToolchainAssertion, match="non dev API key used in dev env!"):
        init_stripe(tc_env=ToolchainEnv.DEV, secrets_reader=secrets_accessor)  # type: ignore[attr-defined]
    assert stripe.api_key == "no-soup-for-you"

    secrets_accessor.set_secret("stripe-integration", json.dumps({"api-key": "david_test_puddy"}))
    with pytest.raises(ToolchainAssertion, match="Dev mode API key used in production"):
        init_stripe(tc_env=ToolchainEnv.PROD, secrets_reader=secrets_accessor)  # type: ignore[attr-defined]
    assert stripe.api_key == "no-soup-for-you"


def test_init_stripe_invalid_secret(secrets_accessor: SecretsAccessor) -> None:
    with pytest.raises(SecretNotFound, match="Secret 'stripe-integration' not found."):
        init_stripe(tc_env=ToolchainEnv.DEV, secrets_reader=secrets_accessor)  # type: ignore[attr-defined]
    secrets_accessor.set_secret("stripe-integration", json.dumps({"david": "jambalaya"}))
    with pytest.raises(KeyError, match="'api-key'"):
        init_stripe(tc_env=ToolchainEnv.DEV, secrets_reader=secrets_accessor)  # type: ignore[attr-defined]


def test_init_stripe() -> None:
    secrets_accessor = DummySecretsAccessor.create_rotatable()
    secrets_accessor.set_secret("stripe-integration", json.dumps({"api-key": "jambalaya"}))
    init_stripe(tc_env=ToolchainEnv.PROD, secrets_reader=secrets_accessor)  # type: ignore[attr-defined]
    assert stripe.api_key == "jambalaya"
