# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.base.password import generate_password


def test_generate_password_default_length():
    pw1 = generate_password()
    assert len(pw1) == 40
    pw2 = generate_password()
    assert len(pw2) == 40
    assert pw1 != pw2


def test_generate_password_custom_length():
    pw1 = generate_password(length=12)
    assert len(pw1) == 12
    pw2 = generate_password(34)
    assert len(pw2) == 34
