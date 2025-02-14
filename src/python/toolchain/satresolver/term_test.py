# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.satresolver.term import RootConstraint, VersionConstraint
from toolchain.satresolver.test_helpers.core_test_data import Groups, Packages, PackageVersions, Terms


class TestVersionConstraint:
    def test_equal(self):
        assert Terms.TERM_AA_100 == VersionConstraint(Packages.AA, {PackageVersions.AA_100}, True, Groups.AA_ALL)
        assert Terms.TERM_AA_100 != VersionConstraint(
            Packages.AB, {PackageVersions.AB_100}, True, {PackageVersions.AB_100}
        )
        assert Terms.TERM_AA_100 != VersionConstraint(Packages.AA, {PackageVersions.AA_200}, True, Groups.AA_ALL)
        assert Terms.TERM_AA_100 != VersionConstraint(Packages.AA, {PackageVersions.AA_100}, False, Groups.AA_ALL)

    def test_not_equal(self):
        assert Terms.TERM_AA_100 == VersionConstraint(Packages.AA, {PackageVersions.AA_100}, True, Groups.AA_ALL)
        assert Terms.TERM_AA_100 != VersionConstraint(
            Packages.AB, {PackageVersions.AB_100}, True, {PackageVersions.AB_100}
        )
        assert Terms.TERM_AA_100 != VersionConstraint(Packages.AA, {PackageVersions.AA_200}, True, Groups.AA_ALL)
        assert Terms.TERM_AA_100 != VersionConstraint(Packages.AA, {PackageVersions.AA_100}, False, Groups.AA_ALL)

    def test_allowed_versions(self):
        assert Terms.TERM_AA_100.allowed_versions == {PackageVersions.AA_100}
        assert Terms.TERM_NOT_AA_100.allowed_versions == {
            PackageVersions.AA_200,
            PackageVersions.AA_300,
            PackageVersions.AA_400,
        }

    def test_satisfies(self):
        # VersionConstraints with different packages cannot satisfy one another.
        with pytest.raises(ValueError, match="a:b:1.0.0 refers to a:b, not a:a."):
            Terms.TERM_AA_100.satisfies(Terms.TERM_AB_100)

        # If both terms are positive, the second is satisfied only if the first is a subset of the second.
        assert not Terms.TERM_AA_100.satisfies(Terms.TERM_AA_200)
        assert not Terms.TERM_AA_12.satisfies(Terms.TERM_AA_200)
        assert Terms.TERM_AA_100.satisfies(Terms.TERM_AA_12)

        # If both terms are negative, the second is satisfied only if the second is a subset of the first.
        assert Terms.TERM_NOT_AA_ALL.satisfies(Terms.TERM_NOT_AA_100) is True
        assert Terms.TERM_NOT_AA_100.satisfies(Terms.TERM_NOT_AA_200) is False
        assert Terms.TERM_NOT_AA_100.satisfies(Terms.TERM_NOT_AA_12) is False
        assert Terms.TERM_NOT_AA_12.satisfies(Terms.TERM_NOT_AA_100) is True

        # If the first VersionConstraint is negative, we cannot conclude anything about the positive term.
        assert Terms.TERM_NOT_AA_100.satisfies(Terms.TERM_AA_200) is False
        assert Terms.TERM_NOT_AA_100.satisfies(Terms.TERM_AA_12) is False
        assert Terms.TERM_NOT_AA_12.satisfies(Terms.TERM_AA_100) is False

        # If the first term is positive and the second negative, the second is True only if it has no elements in common with the first.
        assert Terms.TERM_AA_100.satisfies(Terms.TERM_NOT_AA_200)
        assert Terms.TERM_AA_100.satisfies(Terms.TERM_NOT_AA_12) is False

    def test_inverse(self):
        assert Terms.TERM_AA_100.inverse() == Terms.TERM_NOT_AA_100
        assert Terms.TERM_NOT_AA_100.inverse() == Terms.TERM_AA_100

    def test_intersect(self):
        # VersionConstraints with different packages cannot intersect one another.
        with pytest.raises(ValueError, match="a:b:1.0.0 refers to a:b, not a:a."):
            Terms.TERM_AA_100.intersect(Terms.TERM_AB_100)
        # Both terms positive
        assert Terms.TERM_AA_100.intersect(Terms.TERM_AA_12) == Terms.TERM_AA_100
        assert Terms.TERM_AA_100.intersect(Terms.TERM_AA_200) is None
        # Both terms negative
        assert Terms.TERM_NOT_AA_100.intersect(Terms.TERM_NOT_AA_200) == Terms.TERM_NOT_AA_12
        # One positive, one negative
        assert Terms.TERM_AA_100.intersect(Terms.TERM_NOT_AA_234) == Terms.TERM_AA_100
        assert Terms.TERM_NOT_AA_12.intersect(Terms.TERM_AA_234) == Terms.TERM_AA_34
        assert Terms.TERM_NOT_AA_100.intersect(Terms.TERM_AA_100) is None

    def test_difference(self):
        # VersionConstraints with different packages cannot be subtracted from one another.
        with pytest.raises(ValueError, match="a:b:1.0.0 refers to a:b, not a:a."):
            Terms.TERM_AA_100.difference(Terms.TERM_AB_100)
        # subtract a positive from a positive
        assert Terms.TERM_AA_12.difference(Terms.TERM_AA_234) == Terms.TERM_AA_100
        assert Terms.TERM_AA_100.difference(Terms.TERM_AA_100) is None
        # subtract a negative from a positive
        assert Terms.TERM_AA_12.difference(Terms.TERM_NOT_AA_234) == Terms.TERM_AA_200
        assert Terms.TERM_AA_100.difference(Terms.TERM_NOT_AA_234) is None
        # subtract a positive from a negative
        assert Terms.TERM_NOT_AA_200.difference(Terms.TERM_AA_234) == Terms.TERM_AA_100
        assert Terms.TERM_NOT_AA_100.difference(Terms.TERM_AA_234) is None
        # subtract a negative from a negative
        assert Terms.TERM_NOT_AA_12.difference(Terms.TERM_NOT_AA_234) == Terms.TERM_AA_34
        assert Terms.TERM_NOT_AA_100.difference(Terms.TERM_NOT_AA_100) is None

    def test_str(self):
        assert str(Terms.TERM_AA_100) == "a:a:1.0.0"
        assert str(Terms.TERM_AA_12) == "(a:a:1.0.0, a:a:2.0.0)"
        assert str(Terms.TERM_NOT_AA_100) == "not a:a:1.0.0"
        assert str(Terms.TERM_NOT_AA_12) == "not (a:a:1.0.0, a:a:2.0.0)"
        assert str(Terms.TERM_AA_ALL) == "a:a:Any"
        assert str(Terms.TERM_NOT_AA_ALL) == "not a:a:Any"


class TestRootConstraintTest:
    def test_equal(self):
        assert RootConstraint(is_positive=True) == RootConstraint(is_positive=True)

    def test_not_equal(self):
        assert RootConstraint(is_positive=True) != RootConstraint(is_positive=False)

    def test_inverse(self):
        assert RootConstraint(is_positive=True).inverse() == RootConstraint(is_positive=False)

    def test_satisfies(self):
        assert RootConstraint(is_positive=True).satisfies(RootConstraint(is_positive=True)) is True
        assert RootConstraint(is_positive=True).satisfies(RootConstraint(is_positive=False)) is False

    def test_intersect(self):
        assert RootConstraint(is_positive=True).intersect(RootConstraint(is_positive=True)) == RootConstraint(
            is_positive=True
        )
        assert RootConstraint(is_positive=True).intersect(RootConstraint(is_positive=False)) is None

    def test_difference(self):
        assert RootConstraint(is_positive=True).difference(RootConstraint(is_positive=True)) is None, None
        assert RootConstraint(is_positive=True).difference(RootConstraint(is_positive=False)) == RootConstraint(
            is_positive=True
        )

    def test_str(self):
        assert str(RootConstraint(is_positive=True)) == "__ROOT__"
        assert str(RootConstraint(is_positive=False)) == "not __ROOT__"
