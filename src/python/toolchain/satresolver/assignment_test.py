# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.assignment import Assignment
from toolchain.satresolver.cause import DependencyCause, IncompatibilityCause
from toolchain.satresolver.incompatibility import Incompatibility
from toolchain.satresolver.test_helpers.core_test_data import Packages, Terms

AA_100_DEPENDS_ON_AB_100 = Incompatibility(terms=[Terms.TERM_AA_100, Terms.TERM_NOT_AB_100], cause=DependencyCause())

BA_100_DEPENDS_ON_BB_ANY = Incompatibility(terms=[Terms.TERM_BA_100, Terms.TERM_NOT_BB_ALL], cause=DependencyCause())

ASSIGNMENT_BB_ALL = Assignment(
    term=Terms.TERM_BB_ALL, cause=IncompatibilityCause(BA_100_DEPENDS_ON_BB_ANY), decision_level=0, index=0
)

ASSIGNMENT_AA_100 = Assignment(term=Terms.TERM_AA_100, cause=None, decision_level=1, index=1)

ASSIGNMENT_AB_100 = Assignment(
    term=Terms.TERM_AB_100, cause=IncompatibilityCause(AA_100_DEPENDS_ON_AB_100), decision_level=1, index=2
)


def test_less_than():
    assert ASSIGNMENT_BB_ALL < ASSIGNMENT_AB_100
    assert sorted([ASSIGNMENT_AA_100, ASSIGNMENT_BB_ALL, ASSIGNMENT_AB_100]) == [
        ASSIGNMENT_BB_ALL,
        ASSIGNMENT_AA_100,
        ASSIGNMENT_AB_100,
    ]


def test_is_decision():
    assert not ASSIGNMENT_BB_ALL.is_decision
    assert ASSIGNMENT_AA_100.is_decision


def test_package():
    assert ASSIGNMENT_BB_ALL.subject == Packages.BB
