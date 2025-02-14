# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest

from toolchain.util.secret.secrets_accessor import DummySecretsAccessor, TrackingSecretsReader


@pytest.fixture()
def secrets_accessor():
    secrets_accessor = DummySecretsAccessor.create_rotatable()
    secrets_accessor.set_secret("frank", "hello newman!")
    secrets_accessor.set_secret("kenny", "no soup for you")
    secrets_accessor.set_secret("puddy", json.dumps({"kramer": 33, "apt": "5a"}))
    yield secrets_accessor
    TrackingSecretsReader.clear()


def assert_secrets(client, secrets_dict):
    response = client.get("/checksz/secretsz")
    assert response.status_code == 200
    assert response.json() == {"loaded": secrets_dict}


def test_empty(client):
    assert_secrets(client, {})


def test_secrets_access(client, settings, secrets_accessor):
    reader = settings.SECRETS_READER
    reader.get_secret_or_raise("frank")
    reader.get_json_secret_or_raise("puddy")
    assert_secrets(
        client,
        {
            "puddy": "8e632d202b5d7a16da0f9f78ac98dbb12a07bbae2e9e681ad030faa2546d73c3",
            "frank": "0fe7c541620ac5a9f4cd0ea0e653eb6641143a0fb58ed65b9cee99836dd7b775",
        },
    )
    # this should not cause the version to change since we report the versions of the secrets
    # that were returned via get_secret
    secrets_accessor.set_secret("frank", "I choose not to run")
    assert_secrets(
        client,
        {
            "puddy": "8e632d202b5d7a16da0f9f78ac98dbb12a07bbae2e9e681ad030faa2546d73c3",
            "frank": "0fe7c541620ac5a9f4cd0ea0e653eb6641143a0fb58ed65b9cee99836dd7b775",
        },
    )
    reader.get_secret("kenny")
    assert_secrets(
        client,
        {
            "puddy": "8e632d202b5d7a16da0f9f78ac98dbb12a07bbae2e9e681ad030faa2546d73c3",
            "frank": "0fe7c541620ac5a9f4cd0ea0e653eb6641143a0fb58ed65b9cee99836dd7b775",
            "kenny": "d06dea335390ec77fa6be10795c812b5d1517930eb9b51342109a7337110070f",
        },
    )
