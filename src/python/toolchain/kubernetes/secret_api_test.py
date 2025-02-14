# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.secret_api import SecretAPI


def test_secret_name_validation():
    def check_valid(s):
        SecretAPI.validate_secret_name(s)

    def check_invalid(s):
        with pytest.raises(ToolchainAssertion, match=r"Kubernetes Secret name must .+"):
            SecretAPI.validate_secret_name(s)

    check_valid("foo")
    check_valid("foo-bar")
    check_valid("foo2-bar-33.baz")
    check_invalid("foo_bar")
    check_invalid("foo/bar")
    check_invalid("Foo")


def test_key_validation():
    def check_valid(key):
        SecretAPI.validate_key(key)

    def check_invalid(key):
        with pytest.raises(ToolchainAssertion, match=r"Key in Kubernetes Secret must .+"):
            SecretAPI.validate_key(key)

    check_valid("foo0123")
    check_valid("foo_-.")
    check_invalid("foo#")
    check_invalid("$foo")
