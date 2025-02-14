# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.packagerepo.maven.version.maven_semantic_version import (
    MavenSemver,
    MavenSemverPart,
    canonicalize_version_string,
)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1-1.foo-bar1baz-.1", "1-1.foo-bar-1-baz-0.1"),
        ("foo.10", "foo.10"),
        ("1.0.0", "1"),
        ("1.ga", "1"),
        ("1.final", "1"),
        ("1.0", "1"),
        ("1.", "1"),
        ("1-", "1"),
        ("1.0.0-foo.0.0", "1-foo"),
        ("1a1", "1-alpha-1"),
        ("b1", "beta-1"),
        ("1.foo_bar_people_do%this.1", "1.foo_bar_people_do%this.1"),
    ],
)
def test_canonicalize_version_string(version, expected):
    assert canonicalize_version_string(version) == expected


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # number padding
        ("1", "1.1"),
        # qualifier padding
        ("1-alpha", "1"),
        ("1", "1-sp"),
        # correctly automatically "switching" to numeric order
        ("1-foo2", "1-foo10"),
        # prefix ordering
        ("1.foo", "1-foo"),
        ("1-1", "1.1"),
        ("1-2", "1.1"),
        # non-numeric < numeric
        ("1.foo", "1.1"),
        # removal of trailing "null" values
        ("1-ga", "1-sp"),
        # Special strings
        ("1-ga.1", "1-sp.1"),
        # "1-sp-1" < "1-ga-1" = "1-1" (trailing "null" values at each hyphen)
        ("1-sp-1", "1-ga-1"),
    ],
)
def test_maven_semver_lt(left, right):
    assert MavenSemver(left) < MavenSemver(right)


@pytest.mark.parametrize(("left", "right"), [("1", "1")])
def test_maven_semver_not_lt(left, right):
    assert MavenSemver(left) >= MavenSemver(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("1.ga", "1-ga"),
        ("1-ga", "1.0"),
        ("1.0", "1"),
        ("1-ga-1", "1-1"),
        # Expansion of special characters
        ("1-a1", "1-alpha-1"),
    ],
)
def test_maven_semver_eq(left, right):
    assert MavenSemver(left) == MavenSemver(right)


@pytest.mark.parametrize(
    ("left_prefix", "left_token", "right_prefix", "right_token"),
    [(".", "1", ".", "1"), ("-", "final", "-", ""), (".", "rc", ".", "cr")],
)
def test_maven_semver_part_eq(left_prefix, left_token, right_prefix, right_token):
    assert MavenSemverPart(left_prefix, left_token) == MavenSemverPart(right_prefix, right_token)


@pytest.mark.parametrize(
    ("left_prefix", "left_token", "right_prefix", "right_token"),
    [(".", "1", "-", "1"), ("", "1", "", "2"), ("-", "foo", ".", "foo")],
)
def test_maven_semver_part_neq(left_prefix, left_token, right_prefix, right_token):
    assert MavenSemverPart(left_prefix, left_token) != MavenSemverPart(right_prefix, right_token)


@pytest.mark.parametrize(
    ("left_prefix", "left_token", "right_prefix", "right_token"),
    [(".", "beta", "-", "alpha"), (".", "alpha", ".", "beta"), ("-", "1", ".", "1"), (".", "foo", "-", "foo")],
)
def test_maven_semver_part_lt(left_prefix, left_token, right_prefix, right_token):
    assert MavenSemverPart(left_prefix, left_token) < MavenSemverPart(right_prefix, right_token)
