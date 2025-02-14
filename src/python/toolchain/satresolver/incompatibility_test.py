# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.cause import ConflictCause, DependencyCause, RootCause
from toolchain.satresolver.incompatibility import Incompatibility
from toolchain.satresolver.test_helpers.core_test_data import PackageVersions, Terms

ROOT_INCOMPATIBILITY = Incompatibility(terms=[Terms.TERM_ROOT], cause=RootCause())

ROOT_DEPENDS_ON_AB_200 = Incompatibility(terms=[Terms.TERM_ROOT, Terms.TERM_NOT_AB_200], cause=DependencyCause())

ROOT_DEPENDS_ON_AA_100 = Incompatibility(terms=[Terms.TERM_ROOT, Terms.TERM_NOT_AA_100], cause=DependencyCause())

AA_100_DEPENDS_ON_AB_100 = Incompatibility(terms=[Terms.TERM_AA_100, Terms.TERM_NOT_AB_100], cause=DependencyCause())

ROOT_CONFLICT_WITH_AA_100 = Incompatibility(
    terms=[Terms.TERM_ROOT, Terms.TERM_AA_100], cause=ConflictCause(AA_100_DEPENDS_ON_AB_100, ROOT_DEPENDS_ON_AB_200)
)


def test_is_failure():
    assert not ROOT_DEPENDS_ON_AB_200.is_failure
    assert ROOT_INCOMPATIBILITY.is_failure


def test_str():
    assert str(ROOT_INCOMPATIBILITY) == "__ROOT__ is incompatible"
    assert str(ROOT_DEPENDS_ON_AB_200) == f"__ROOT__ depends on {PackageVersions.AB_200}"
    assert str(ROOT_CONFLICT_WITH_AA_100) == f"__ROOT__ is incompatible with {PackageVersions.AA_100}"
