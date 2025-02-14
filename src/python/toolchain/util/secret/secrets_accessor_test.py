# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest

from toolchain.util.secret.secrets_accessor import (
    ChainedSecretsReader,
    DummySecretsAccessor,
    RotatableSecretsAccessor,
    SecretNotFound,
    TrackingSecretsReader,
)


def test_chained_accessor():
    sa1 = DummySecretsAccessor()
    sa2 = DummySecretsAccessor()
    chained = ChainedSecretsReader(sa1, sa2)
    assert chained.get_secret("jerry") is None
    sa1.set_secret("jerry", "seinfeld")
    sa2.set_secret("jerry", "jerome")
    sa2.set_secret("george", "costanza")
    sa1.set_secret("cosmo", None)
    sa2.set_secret("cosmo", "kramer")
    sa1.set_secret("Kenny", "")
    sa2.set_secret("Kenny", "bania")

    assert chained.get_secret("jerry") == "seinfeld"
    assert chained.get_secret("cosmo") == "kramer"

    assert chained.get_secret("Kenny") == ""
    assert chained.get_version("Kenny") is None
    assert chained.get_secret_and_version("Kenny") == ("", None)

    assert chained.get_secret("george") == "costanza"
    assert chained.get_version("george") == "9d943354ef5e7ed7c79383a2c241408bdc3bc4e3050a66871746bd56014c24c0"
    assert chained.get_secret_and_version("george") == (
        "costanza",
        "9d943354ef5e7ed7c79383a2c241408bdc3bc4e3050a66871746bd56014c24c0",
    )


def test_tracking_secrets_reader():
    sa = DummySecretsAccessor()
    trackable = TrackingSecretsReader(sa)
    sa.set_secret("jerry", "seinfeld")
    sa.set_secret("george", "costanza")
    sa.set_secret("cosmo", "kramer")
    sa.set_secret("Kenny", "bania")
    assert not TrackingSecretsReader.get_tracked_secrets()
    trackable.get_secret("jerry")
    trackable.get_secret("kramer")
    trackable.get_secret("jerry")
    assert TrackingSecretsReader.get_tracked_secrets() == {
        "jerry": "0c957e9f09a2444a8868737bf42b16f40d4e3533b57dc31a61124c2cd1bae31b",
        "kramer": None,
    }
    # make sure caller can't change state for TrackableSecretsReader
    TrackingSecretsReader.get_tracked_secrets().update(elaine="no soup for you")
    assert TrackingSecretsReader.get_tracked_secrets() == {
        "jerry": "0c957e9f09a2444a8868737bf42b16f40d4e3533b57dc31a61124c2cd1bae31b",
        "kramer": None,
    }
    trackable.get_secret("bania")
    trackable.get_secret("kramer")
    assert TrackingSecretsReader.get_tracked_secrets() == {
        "bania": None,
        "jerry": "0c957e9f09a2444a8868737bf42b16f40d4e3533b57dc31a61124c2cd1bae31b",
        "kramer": None,
    }
    assert trackable.get_secret_and_version("george") == (
        "costanza",
        "9d943354ef5e7ed7c79383a2c241408bdc3bc4e3050a66871746bd56014c24c0",
    )
    assert trackable.get_version("george") == "9d943354ef5e7ed7c79383a2c241408bdc3bc4e3050a66871746bd56014c24c0"


@pytest.mark.parametrize("compressed", [True, False])
def test_rotatable_secrets_reader(compressed):
    sa = RotatableSecretsAccessor(DummySecretsAccessor(), compressed=compressed)
    sa.set_secret("jerry", "seinfeld")
    sa.set_secret("george", "costanza")
    sa.set_secret("cosmo", json.dumps({"kramer": 33, "apt": "5a"}))
    assert sa.get_version("jerry") == "0c957e9f09a2444a8868737bf42b16f40d4e3533b57dc31a61124c2cd1bae31b"
    assert sa.get_secret("jerry") == "seinfeld"
    assert sa.get_json_secret("cosmo") == {"kramer": 33, "apt": "5a"}
    assert sa.get_version("cosmo") == "8e632d202b5d7a16da0f9f78ac98dbb12a07bbae2e9e681ad030faa2546d73c3"
    sa.set_secret("jerry", "crazy joe davola")
    assert sa.get_version("jerry") == "30377e5a6d9e87c478aa632bb4437d4510a2a5d7821c153852b8c1d7641aba98"
    assert sa.get_secret("jerry") == "crazy joe davola"
    assert sa.get_secret_and_version("jerry") == (
        "crazy joe davola",
        "30377e5a6d9e87c478aa632bb4437d4510a2a5d7821c153852b8c1d7641aba98",
    )


def test_secret_not_found():
    sa = RotatableSecretsAccessor(DummySecretsAccessor(), compressed=True)
    sa.set_secret("jerry", "seinfeld")
    assert sa.get_secret("soup") is None
    assert sa.get_json_secret("soup") is None
    with pytest.raises(SecretNotFound, match="Secret 'soup' not found"):
        sa.get_secret_or_raise("soup")
    with pytest.raises(SecretNotFound, match="Secret 'soup' not found"):
        sa.get_json_secret_or_raise("soup")


def test_secret_not_found_with_note():
    dsa = DummySecretsAccessor()
    dsa.ERROR_NOTE = "It's a European carryall!"
    sa = RotatableSecretsAccessor(dsa, compressed=True)
    sa.set_secret("jerry", "seinfeld")
    assert sa.get_secret("soup") is None
    assert sa.get_json_secret("soup") is None
    with pytest.raises(SecretNotFound, match="Secret 'soup' not found. It's a European carryall!"):
        sa.get_secret_or_raise("soup")
    with pytest.raises(SecretNotFound, match="Secret 'soup' not found. It's a European carryall!"):
        sa.get_json_secret_or_raise("soup")
