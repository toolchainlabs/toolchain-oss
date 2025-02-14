# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.packagerepo.maven.version.maven_semantic_version import MavenSemver
from toolchain.packagerepo.maven.version.maven_semantic_version_spec import MavenVersionSpec


@pytest.mark.parametrize(
    ("spec", "version", "expected"),
    [
        # Hard requirement: x == '1.0'
        ("[1.0]", "1.0", True),
        ("[1.0]", "1.1", False),
        ("[1.0]", "1", True),
        # Inclusive upper bound: (,1.0] x <= 1.0
        ("(,1.0]", "0.9", True),
        ("(,1.0]", "1.0", True),
        ("(,1.0]", "1.1", False),
        # Exclusive upper bound: (,1.0): x < 1.0
        ("(,1.0)", "0.9", True),
        ("(,1.0)", "1.0", False),
        ("(,1.0)", "1.1", False),
        # Inclusive Lower Bound: [1.0,): x >= 1.0
        ("[1.0,)", "0.9", False),
        ("[1.0,)", "1.0", True),
        ("[1.0,)", "16-alpha.12", True),
        # Exclusive Lower Bound: (1.0,): x > 1.0
        ("(1.0,)", "0.9", False),
        ("(1.0,)", "1.0", False),
        ("(1.0,)", "16-alpha.12", True),
        # Inclusive Upper and Lower: [1.2,1.3]: 1.2 <= x <= 1.3
        ("[1.2,1.3]", "1.2", True),
        ("[1.2,1.3]", "1.1", False),
        ("[1.2,1.3]", "1.3", True),
        ("[1.2,1.3]", "1.8", False),
        # Inclusive Lower, Exclusive Upper: [1.0,2.0): 1.0 <= x < 2.0
        ("[1.0,2.0)", "1.0", True),
        ("[1.0,2.0)", "2.0", False),
        # Multiple Ranges: (,1.0],[1.2,): x <= 1.0 or x >= 1.2
        ("(,1.0],[1.2,)", "1.0", True),
        ("(,1.0],[1.2,)", "0.9", True),
        ("(,1.0],[1.2,)", "1.1", False),
        ("(,1.0],[1.2,)", "1.2", True),
        # Exclusion: (,1.1),(1.1,): x < 1.1 or x > 1.1
        ("(,1.1),(1.1,)", "1.1", False),
        ("(,1.1),(1.1,)", "1.0", True),
        ("(,1.1),(1.1,)", "3.0", True),
        # Hard requirement and range combo: '[1.0],[1.2,4.0]' --> x == 1.0 or 1.2 <= x <= 4
        ("[1.0],[1.2,4.0]", "1.0", True),
        ("[1.0],[1.2,4.0]", "1.1", False),
        ("[1.0],[1.2,4.0]", "3.0", True),
    ],
)
def test_maven_version_spec(spec, version, expected):
    assert MavenVersionSpec(spec).is_valid_version(MavenSemver(version)) == expected


def test_maven_version_spec_soft_requirement():
    assert MavenVersionSpec("1.0").soft_requirement == MavenSemver("1.0")
