# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainError
from toolchain.lang.python.distributions.distribution_metadata import extract_metadata
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.lang.python.test_helpers.utils import extract_distribution

# The full metadata is large, so we just spot-check that these key/value pairs are present.
_requests_metadata = {"author": "Kenneth Reitz", "author_email": "me@kennethreitz.org"}
_froglabs_metadata = {"author": "Froglabs, Inc", "author_email": "team@froglabs.ai"}
_fslparser_metadata = {
    "author": "Fatemeh",
    "author_email": "",
    "summary": "fsl-parser",
    "requires_dist": ["pandas (>=0.20.3)"],
    "version": "0.0.2",
    "description": "description containing nul bytes was omitted.",
}

_konfoo_metadata = {
    "author": "Jochen Gerhaeusser",
    "author_email": "jochen_privat@gmx.de",
    "description": "description containing nul bytes was omitted.",
    "home_page": "http://github.com/JoeVirtual/KonFoo",
    "keywords": "binary data deserialize serialize parse decode encode unpack pack",
    "license": "BSD",
    "metadata_version": "2.1",
    "name": "KonFoo",
    "platforms": ["any"],
    "requires_python": ">=3.6",
    "summary": "A declarative byte stream mapping engine.",
    "version": "2.0",
}

_emaildepute_metadata = {"author": "Froglabs, Inc", "author_email": "team@froglabs.ai"}


@pytest.mark.parametrize(
    ("distribution_name", "expected_distribution_type", "expected_metadata"),
    [
        ("requests-2.22.0.tar.gz", DistributionType.SDIST, _requests_metadata),
        ("requests-2.22.0-py2.py3-none-any.whl", DistributionType.WHEEL, _requests_metadata),
        ("froglabs-0.1.3-py3.6.egg", DistributionType.SDIST, _froglabs_metadata),
        ("KonFoo-2.0-py3-none-any.whl", DistributionType.WHEEL, _konfoo_metadata),
        ("fslparser-0.0.2.tar.gz", DistributionType.SDIST, _fslparser_metadata),
    ],
)
def test_extract_metadata(
    distribution_name: str, expected_distribution_type: DistributionType, expected_metadata: dict
) -> None:
    with extract_distribution(distribution_name) as distribution:
        distribution_type, metadata = extract_metadata(distribution)
        assert expected_distribution_type == distribution_type
        assert expected_metadata.items() <= metadata.items()


@pytest.mark.parametrize("distribution_name", ["EmailDepute-1.1.2021.tar.gz"])
def test_extract_metadata_failures(distribution_name: str) -> None:
    with extract_distribution(distribution_name) as distribution, pytest.raises(
        ToolchainError, match="Failed to parse requirement"
    ):
        extract_metadata(distribution)
