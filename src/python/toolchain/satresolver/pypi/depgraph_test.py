# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.lang.python.distributions.distribution_key import DistributionKey
from toolchain.satresolver.pypi.depgraph import Depgraph


@pytest.mark.parametrize(
    ("kwargs", "expected_prefix", "expected_filter"),
    [
        ({"package_name": "foo"}, ["foo"], {}),
        ({"package_name": "foo", "distribution_type": "WHEEL"}, ["foo"], {"distribution_type": "WHEEL"}),
        ({"package_name": "foo", "requires_python": "python3"}, ["foo"], {"requires_python": "python3"}),
        ({"package_name": "foo", "platform": "xyz"}, ["foo"], {"platform": "xyz"}),
        ({"package_name": "foo", "platform": "xyz", "abi": "abc"}, ["foo"], {"platform": "xyz", "abi": "abc"}),
        ({"package_name": "foo", "version": "1.0.0"}, ["foo", "1.0.0"], {}),
        ({"package_name": "foo", "version": "1.0.0", "distribution_type": "WHEEL"}, ["foo", "1.0.0", "WHEEL"], {}),
        (
            {"package_name": "foo", "version": "1.0.0", "requires_python": "python3"},
            ["foo", "1.0.0"],
            {"requires_python": "python3"},
        ),
        ({"package_name": "foo", "version": "1.0.0", "platform": "xyz"}, ["foo", "1.0.0"], {"platform": "xyz"}),
        (
            {"package_name": "foo", "version": "1.0.0", "platform": "xyz", "abi": "abc"},
            ["foo", "1.0.0"],
            {"platform": "xyz", "abi": "abc"},
        ),
        (
            {"package_name": "foo", "version": "1.0.0", "distribution_type": "WHEEL", "requires_python": "python3"},
            ["foo", "1.0.0", "WHEEL", "python3"],
            {},
        ),
        (
            {
                "package_name": "foo",
                "version": "1.0.0",
                "distribution_type": "WHEEL",
                "requires_python": "python3",
                "abi": "abc",
            },
            ["foo", "1.0.0", "WHEEL", "python3"],
            {"abi": "abc"},
        ),
    ],
)
def test_compute_prefix_and_filter(kwargs, expected_prefix, expected_filter) -> None:
    assert (expected_prefix, expected_filter) == Depgraph.compute_prefix_and_filter(**kwargs)


@pytest.mark.parametrize(
    "filter_kwargs",
    [
        {},
        {"package_name": "foo"},
        {"package_name": "foo", "version": "1.0.0"},
        {"version": "1.0.0"},
        {"version": "1.0.0", "platform": "xyz"},
        {"platform": "xyz"},
        {"distribution_type": "WHEEL", "abi": "abc", "build": "123"},
        {
            "package_name": "foo",
            "version": "1.0.0",
            "distribution_type": "WHEEL",
            "requires_python": "python3",
            "platform": "xyz",
            "abi": "abc",
            "build": "123",
        },
    ],
)
def test_positive_filter_key(filter_kwargs) -> None:
    key = DistributionKey(
        package_name="foo",
        version="1.0.0",
        distribution_type="WHEEL",
        requires_python="python3",
        platform="xyz",
        abi="abc",
        build="123",
    )
    assert Depgraph.filter_key(key, **filter_kwargs)


@pytest.mark.parametrize(
    "filter_kwargs",
    [
        {"package_name": "bar"},
        {"package_name": "foo", "version": "1.0.1"},
        {"package_name": "bar", "version": "1.0.0"},
        {"version": "1.0.1"},
        {"version": "1.0.0", "platform": "xyzw"},
        {"platform": "xyzw"},
        {"distribution_type": "SDIST", "abi": "abc", "build": "123"},
        {
            "package_name": "foo",
            "version": "1.0.0",
            "distribution_type": "WHEEL",
            "requires_python": "python3",
            "platform": "xyz",
            "abi": "abc",
            "build": "1234",
        },
    ],
)
def test_negative_filter_key(filter_kwargs) -> None:
    key = DistributionKey(
        package_name="foo",
        version="1.0.0",
        distribution_type="WHEEL",
        requires_python="python3",
        platform="xyz",
        abi="abc",
        build="123",
    )
    assert not Depgraph.filter_key(key, **filter_kwargs)
