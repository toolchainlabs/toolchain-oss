# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution, ResolutionData
from toolchain.satresolver.test_helpers.pypi_test_data import Distributions


@pytest.mark.parametrize("requirements", [[], ["foo==1.2.3", "bar.baz>=3.0,<4"]])
def test_serialization(requirements: list[str]) -> None:
    data = ResolutionData.create(requirements=tuple(requirements), sha256_hexdigest=8 * "deadbeef")
    assert data == ResolutionData.from_bytes(data.to_bytes())


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (Distributions.aaa_201_whl_33, Distributions.aaa_2012_whl_33),
        (Distributions.aaa_100_whl_27_osx, Distributions.aaa_100_whl_27_win),
        (Distributions.aaa_100_whl_27, Distributions.aaa_100_whl_33),
    ],
)
def test_lt(a: PythonPackageDistribution, b: PythonPackageDistribution) -> None:
    assert a < b
