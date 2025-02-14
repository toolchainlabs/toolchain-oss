# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.satresolver.assignment import Assignment
from toolchain.satresolver.cause import DependencyCause, IncompatibilityCause
from toolchain.satresolver.incompatibility import Incompatibility
from toolchain.satresolver.partial_solution import PartialSolution
from toolchain.satresolver.test_helpers.core_test_data import Packages, PackageVersions, Terms

AA_100_DEPENDS_ON_AB_100 = Incompatibility(terms=[Terms.TERM_AA_100, Terms.TERM_NOT_AB_100], cause=DependencyCause())
AC_200_DEPENDS_ON_AB_ANY = Incompatibility(terms=[Terms.TERM_AC_200, Terms.TERM_NOT_AB_ALL], cause=DependencyCause())

ASSIGNMENT_AB_ALL = Assignment(
    term=Terms.TERM_AB_ALL, cause=IncompatibilityCause(AC_200_DEPENDS_ON_AB_ANY), decision_level=1, index=0
)
ASSIGNMENT_AB_100 = Assignment(
    term=Terms.TERM_AB_100, cause=IncompatibilityCause(AA_100_DEPENDS_ON_AB_100), decision_level=1, index=1
)


class TestPartialSolution:
    @pytest.fixture()
    def solution(self):
        return PartialSolution()

    def test_decisions(self, solution):
        solution._decisions = {Packages.AA: Terms.TERM_AA_200, Packages.AB: Terms.TERM_AB_200}
        assert solution.decisions == [PackageVersions.AA_200, PackageVersions.AB_200]

    def test_positive(self, solution):
        solution._terms = {Packages.AA: Terms.TERM_AA_200, Packages.AB: Terms.TERM_NOT_AB_100}
        assert solution._positive == {Packages.AA: Terms.TERM_AA_200}

    def test_unsatisfied(self, solution):
        solution._decisions = {Packages.AC: Terms.TERM_AC_100}
        solution._terms = {
            Packages.AA: Terms.TERM_AA_200,
            Packages.AB: Terms.TERM_NOT_AB_100,
            Packages.AC: Terms.TERM_AC_100,
        }
        assert solution.unsatisfied == {Packages.AA: Terms.TERM_AA_200}

    def test_decision_level(self, solution):
        assert solution.decision_level == 0
        solution._decisions = {Packages.AC: Terms.TERM_AC_100}
        assert solution.decision_level == 1

    def test_decide(self, solution):
        assert solution._attempted_solutions == 1
        assert solution.decision_level == 0
        assert not solution._backtracking

        solution.decide(Terms.TERM_AA_100)
        assert solution._attempted_solutions == 1
        assert solution.decision_level == 1
        assert not solution._backtracking

        solution._backtracking = True
        solution.decide(Terms.TERM_AC_200)
        assert solution._backtracking is False
        assert solution._attempted_solutions == 2
        assert len(solution._assignments) == 2
        assert len(solution._terms) == 2

        assignment = solution._assignments[-1]
        assert assignment.term == Terms.TERM_AC_200
        assert assignment.decision_level == 2
        assert assignment.index == 1
        assert assignment.cause is None
        assert assignment.is_decision

    def test_derive(self, solution):
        solution.derive(term=Terms.TERM_AB_100, cause=AA_100_DEPENDS_ON_AB_100)
        assert solution._attempted_solutions == 1
        assert solution.decision_level == 0
        assignment = solution._assignments[0]
        assert assignment.term == Terms.TERM_AB_100
        assert assignment.decision_level == 0
        assert assignment.index == 0
        assert assignment.cause == AA_100_DEPENDS_ON_AB_100
        assert len(solution._assignments) == 1
        assert len(solution._terms) == 1

    def test_register(self, solution):
        solution._register(ASSIGNMENT_AB_ALL)
        assert solution._terms[Packages.AB] == Terms.TERM_AB_ALL

        solution._register(ASSIGNMENT_AB_100)
        assert solution._terms[Packages.AB] == Terms.TERM_AB_100

    def test_backtrack(self, solution):
        solution.decide(Terms.TERM_AC_200)
        solution.derive(term=Terms.TERM_AB_ALL, cause=AC_200_DEPENDS_ON_AB_ANY)
        solution.decide(Terms.TERM_AA_100)
        solution.derive(term=Terms.TERM_AB_100, cause=AA_100_DEPENDS_ON_AB_100)
        assert solution.decision_level == 2
        assert len(solution._assignments) == 4
        assert solution.decisions == [PackageVersions.AA_100, PackageVersions.AC_200]
        assert solution._terms == {
            Packages.AC: Terms.TERM_AC_200,
            Packages.AB: Terms.TERM_AB_100,
            Packages.AA: Terms.TERM_AA_100,
        }

        solution.backtrack(1)
        assert solution.decision_level == 1
        assert len(solution._assignments) == 2
        assert solution._terms == {Packages.AC: Terms.TERM_AC_200, Packages.AB: Terms.TERM_AB_ALL}
        assert solution.decisions == [PackageVersions.AC_200]

    def test_satisfier(self, solution):
        solution.decide(Terms.TERM_AC_200)
        solution.derive(term=Terms.TERM_AB_ALL, cause=AC_200_DEPENDS_ON_AB_ANY)
        solution.decide(Terms.TERM_AA_100)
        solution.derive(term=Terms.TERM_AB_100, cause=AA_100_DEPENDS_ON_AB_100)
        satisfier = solution.satisfier(Terms.TERM_NOT_AA_300)
        assert satisfier.index == 2
        assert satisfier.term == Terms.TERM_AA_100

    def test_satisfies(self, solution):
        solution._terms = {Packages.AA: Terms.TERM_AA_200, Packages.AB: Terms.TERM_NOT_AB_100}
        assert solution.satisfies(Terms.TERM_AA_200)
        assert not solution.satisfies(Terms.TERM_AA_100)
        assert solution.satisfies(Terms.TERM_NOT_AA_300)
        assert not solution.satisfies(Terms.TERM_AA_100)
        assert not solution.satisfies(Terms.TERM_AB_200)
        assert not solution.satisfies(Terms.TERM_NOT_AB_200)
        assert not solution.satisfies(Terms.TERM_AB_100)
        assert solution.satisfies(Terms.TERM_NOT_AB_100)
        assert not solution.satisfies(Terms.TERM_AC_100)

    def test_is_incompatible(self, solution):
        solution._terms = {Packages.AB: Terms.TERM_AB_100, Packages.AA: Terms.TERM_NOT_AA_100}
        assert not solution.is_incompatible(Terms.TERM_AB_100)
        assert solution.is_incompatible(Terms.TERM_AB_200)
        assert not solution.is_incompatible(Terms.TERM_NOT_AB_200)
        assert solution.is_incompatible(Terms.TERM_NOT_AB_100)
        assert not solution.is_incompatible(Terms.TERM_AA_200)
        assert solution.is_incompatible(Terms.TERM_AA_100)
        assert not solution.is_incompatible(Terms.TERM_NOT_AA_100)
        assert not solution.is_incompatible(Terms.TERM_AC_100)
