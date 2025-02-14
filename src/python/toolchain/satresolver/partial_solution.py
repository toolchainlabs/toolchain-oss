# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.satresolver.assignment import Assignment
from toolchain.satresolver.cause import Cause
from toolchain.satresolver.package import PackageVersion
from toolchain.satresolver.term import Term, VersionConstraint
from toolchain.util.logging.style_adapter import StyleAdapter

logger = StyleAdapter(logging.getLogger(__name__))


class PartialSolution:
    """The state of our current solution."""

    def __init__(self) -> None:
        # All assignments made in this partial solution in the order in which they were made. There may be multiple
        # assignments referencing the same subject. Used to reconstruct state when backtracking.
        self._assignments: list[Assignment] = []
        # A map of subject: Term. All Terms in _decisions are positive.
        # If the Term is a VersionConstraint it will include a single PackageVersion.
        self._decisions: dict[str, Term] = {}
        # A map of subject: Term where the Term is the intersection of all assignments relating to this subject.
        self._terms: dict[str, Term] = {}
        self._attempted_solutions: int = 1
        self._backtracking: bool = False

    @property
    def decisions(self) -> list[PackageVersion]:
        """Returns a sorted list of PackageVersions for all packages that have been decided."""
        versions: set[PackageVersion] = set()
        version_constraints = [term for term in self._decisions.values() if isinstance(term, VersionConstraint)]
        for term in version_constraints:
            versions = versions.union(term.versions)
        return sorted(versions)

    @property
    def _positive(self) -> dict[str, Term]:
        """Returns all positive terms in the current solution as a dictionary of subject: Term."""
        return {subject: term for subject, term in self._terms.items() if term.is_positive}

    @property
    def unsatisfied(self) -> dict[str, Term]:
        """Returns required packages that are not yet decided as a dictionary of subject: Term."""
        return {subject: term for subject, term in self._positive.items() if subject not in self._decisions}

    @property
    def decision_level(self) -> int:
        """The number of decisions made so far."""
        return len(self._decisions)

    def decide(self, term: Term) -> None:
        """Add an assignment of package as a decision and increment decision_level."""
        if self._backtracking:
            self._attempted_solutions += 1
            self._backtracking = False
        self._decisions[term.subject] = term
        assignment = Assignment(term=term, decision_level=self.decision_level, index=len(self._assignments))
        logger.debug("Decided {}", assignment)
        self._assignments.append(assignment)
        self._register(assignment)

    def derive(self, term: Term, cause: Cause) -> None:
        """Add an assignment of package as a derivation."""
        assignment = Assignment(
            term=term, decision_level=self.decision_level, index=len(self._assignments), cause=cause
        )
        logger.debug("Derived {}", assignment)
        self._assignments.append(assignment)
        self._register(assignment)

    def _register(self, assignment: Assignment) -> None:
        """Add assignment to terms, updating the existing term as necessary."""
        old_term = self._terms.get(assignment.subject)
        self._terms[assignment.subject] = (
            old_term.intersect(assignment.term) if old_term is not None else assignment.term
        )

    def backtrack(self, decision_level: int) -> None:
        """Resets the current decision level to decision_level and removes all assignments made after that level."""
        # It is possible we will call this method more than once in the course of resolving a conflict.
        # The number of attempted solutions will be incremented when we next make a decision, indicating that the
        # incompatibility representing the conflict has been propagated and the conflict fully resolved.
        self._backtracking = True
        removed = set()
        while self._assignments[-1].decision_level > decision_level:
            removed.add(self._assignments.pop().subject)

        for subject in removed:
            self._terms.pop(subject, None)
            self._decisions.pop(subject, None)

        # Reconstruct the current term for affected packages.
        for assignment in self._assignments:
            if assignment.subject in removed:
                self._register(assignment)

    def satisfier(self, term: Term) -> Assignment | None:
        """Returns the first assignment in this solution where term is satisfied."""
        assignments_for_package = [assignment for assignment in self._assignments if assignment.subject == term.subject]
        current_term = None
        for assignment in assignments_for_package:
            if current_term is None:
                current_term = assignment.term
            else:
                current_term = current_term.intersect(assignment.term)
            if current_term.satisfies(term):
                return assignment
        return None

    def satisfies(self, term: Term) -> bool:
        """Returns whether this solution satisfies term."""
        current_term = self._terms.get(term.subject)
        return current_term.satisfies(term) if current_term is not None else False

    def is_incompatible(self, term: Term) -> bool:
        """Returns whether term is incompatible with this solution."""
        current_term = self._terms.get(term.subject)
        return current_term.intersect(term) is None if current_term is not None else False
