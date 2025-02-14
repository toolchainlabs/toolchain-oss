# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.pypi.platforms import Platform


def test_lt():
    assert Platform("any") < Platform("macosx_10_10_intel")
    assert Platform("any") < Platform("linux_x86_64")


def test_gt():
    assert Platform("linux_x86_64") > Platform("any")


def test_eq():
    assert Platform("any") == Platform("any")
