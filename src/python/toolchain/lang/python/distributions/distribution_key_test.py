# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.lang.python.distributions.distribution_key import (
    DistributionKey,
    parse_filename,
    python_requirement_from_tag,
)
from toolchain.lang.python.distributions.distribution_type import DistributionType


def test_parse_filename():
    assert ("bbb", "1.0.0", None, None, "py33", "none", "any") == parse_filename(
        "bbb-1.0.0-py33-none-any.whl", DistributionType.WHEEL
    ).groups()
    assert ("foo", "1.0.0", "py27", None) == parse_filename("foo-1.0.0-py27.egg", DistributionType.BDIST).group(
        "name", "version", "python", "platform"
    )


def test_python_requirement_from_tag():
    assert python_requirement_from_tag("py27") == "~=2.7"
    assert python_requirement_from_tag("py2") == ">2,<3"
    assert python_requirement_from_tag("py2.py3") == ">=2,<4"
    assert python_requirement_from_tag("py33") == "~=3.3"
    assert (
        python_requirement_from_tag(
            "py2.py3.cp26.cp27.cp32.cp33.cp34.cp35.cp36.cp37.cp38.pp27.pp32.pp33.pp34.pp35.pp36"
        )
        == ">=2,<4"
    )
    assert python_requirement_from_tag("py2.py26.py36.py37.py38") == ">=2,<=3.8"


def test_create_python_package_distribution_key():
    key = DistributionKey.create(
        "aaa-1.0.0-py27-none-any.whl", "aaa", "1.0.0", DistributionType.WHEEL.value, "python>=3.3"
    )
    assert DistributionKey("aaa", "1.0.0", DistributionType.WHEEL.value, "python>=3.3", "any", "none", "") == key


def test_serialization():
    key = DistributionKey.create(
        "pantsbuild.pants-1.17.0-cp36-abi3-manylinux1_x86_64.whl",
        "pantsbuild.pants",
        "1.17.0",
        DistributionType.WHEEL.value,
        "",
    )
    assert key == DistributionKey.from_ordered_bytes(key.to_ordered_bytes())
