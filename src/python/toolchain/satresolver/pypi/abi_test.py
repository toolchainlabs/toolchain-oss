# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.pypi.abi import ABI


def test_lt() -> None:
    assert ABI("abi3") < ABI("cp38m")


def test_gt() -> None:
    assert ABI("cp38m") > ABI("cp35m")


def test_eq() -> None:
    assert ABI("abi3") == ABI("abi3")
