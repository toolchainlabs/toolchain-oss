# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Iterable

from toolchain.base.toolchain_error import ToolchainError
from toolchain.satresolver.assignment import Assignment
from toolchain.satresolver.cause import ConflictCause, IncompatibilityCause, NoVersionsCause, PackageNotFoundCause
from toolchain.satresolver.config import Config
from toolchain.satresolver.incompatibility import Incompatibility
from toolchain.satresolver.package import ROOT, PackageVersion
from toolchain.satresolver.partial_solution import PartialSolution
from toolchain.satresolver.report import Report
from toolchain.satresolver.simple_result_graph import ResultGraph
from toolchain.satresolver.term import RootConstraint, Term, VersionConstraint
from toolchain.util.logging.style_adapter import StyleAdapter

logger = StyleAdapter(logging.getLogger(__name__))


class ResolutionError(ToolchainError):
    """The resolve failed."""

    def __init__(self, error_message: str, failure: Incompatibility):
        super().__init__(error_message)
        self._failure = failure

    def get_failure_error_message(self) -> str:
        return "\n".join(line.message for line in Report(self._failure).construct_error_message())

    def to_dict(self) -> dict:
        # Creating an actual useful structured representation of the Incompatibility object is not trivial, so punting on it for now.
        # We should revisit this in the future.
        return {"msg": self.get_failure_error_message()}


# The core of the resolver works as follows:

# - Begin by adding RootConstraint to the PartialSolution and all of RootConstraints incompatibilities to our collection of
#  incompatibilities.

# - Let CURRENT be the subject of the RootConstraint.

# - In a loop:

#   - Check each known Incompatibility of CURRENT against our partial solution, deriving new assignments if possible.
#     (See https://github.com/dart-lang/pub/blob/master/doc/solver.md#unit-propagation for more details on this process.)
#
#     - If this process reveals a conflict in our partial solution, attempt to resolve it. If conflict resolution fails,
#       version solving has failed and we report the error.

#   - Once there are no more derivations to be found, make a decision and set CURRENT to the subject returned by the
#     decision-making process.

#     - Decision making may determine that there's no more work to do, in which case version solving is done and the
#       partial solution represents a total solution.


class Resolver:
    def __init__(self, config: Config):
        """Finds a set of dependencies that match the constraints of root.

        Throws a ResolutionError if no solution is available.
        """
        self._incompatibilities: defaultdict = defaultdict(list)
        self._solution: PartialSolution = PartialSolution()
        self._config: Config = config
        self._has_run: bool = False
        self.loop_iterations = 0

    def _setup_root(self) -> None:
        """Add incompatibilities for root and seed the solution with the RootConstraint."""
        root_incompatibilities = self._config.root_incompatibilities()
        for incompatibility in root_incompatibilities:
            self._add_incompatibility(incompatibility)
        self._solution.decide(RootConstraint.require())

    def run(self) -> list[PackageVersion]:
        """Returns a valid solution for the given graph and configuration.

        Will run only once, repeated runs will return the existing result.
        """
        if not self._has_run:
            self.has_run = True
            self._solve()
        return self.result()

    def _solve(self) -> None:
        """Computes a valid solution for the given graph and configuration."""
        self._setup_root()
        current: str | None = ROOT.package_name
        while current is not None:
            self.loop_iterations += 1
            self._propagate(current)
            current = self._choose_package_version()

    def _add_incompatibility(self, incompatibility: Incompatibility) -> None:
        logger.debug("Fact: {}", incompatibility)
        for term in incompatibility.terms:
            self._incompatibilities[term.subject].append(incompatibility)

    def _propagate(self, subject: str) -> None:
        """Performs unit propagation on incompatibilities transitively related to subject to derive new assignments."""
        changed: deque = deque()
        changed.append(subject)
        while changed:
            current_subject = changed.popleft()
            logger.debug(f"Propagating {current_subject}")
            for incompatibility in self._incompatibilities[current_subject]:
                result = self._propagate_incompatibility(incompatibility)
                if isinstance(result, Incompatibility):
                    root_cause = self._resolve_conflict(incompatibility)
                    changed.append(self._propagate_incompatibility(root_cause))
                elif result is not None:
                    changed.append(result)

    def _propagate_incompatibility(self, incompatibility: Incompatibility) -> Incompatibility | str | None:
        """Check `incompatibility` against the current solution and attempt to derive new assignments."""
        logger.debug(f"Propagating incompatibility: {incompatibility}")
        unsatisfied_term = None
        for term in incompatibility.terms:
            if self._solution.satisfies(term):
                logger.debug("Solution satisfies {}.", term)
                continue
            # Term is already contradicted by solution and so is incompatibility.
            if self._solution.is_incompatible(term):
                logger.debug(f"Solution is incompatible with {term}.")
                return None
            # More than one term is inconclusive, so we cannot learn anything more.
            if unsatisfied_term is not None:
                logger.debug(
                    f"Solution is inconclusive for {incompatibility}. Both {unsatisfied_term} and {term} are unsatisfied"
                )
                return None

            unsatisfied_term = term

        if unsatisfied_term is None:
            # If all terms in `incompatibility` are satisfied by our current solution we have a conflict.
            logger.debug(f"CONFLICT: Solution satisfies all terms in {incompatibility}.")
            return incompatibility
        # Exactly one term in incompatibility is unsatisfied, therefore the inverse of the unsatisfied term can be added
        # to our solution.
        # ex: if `foo:1.0.0` is incompatible with `not bar:1.0.0` and `foo:1.0.0` is satisfied by our solution, we can
        # derive that `bar:1.0.0` must be added to our solution.
        # The reverse is also true - if `not bar:1.0.0` is satisfied by our solution (maybe because we decided on `bar:2.0.0`)
        # then we derive `not foo:1.0.0`
        logger.debug(f"{incompatibility} has exactly one term not satisfied by solution: {unsatisfied_term}.")
        self._solution.derive(term=unsatisfied_term.inverse(), cause=IncompatibilityCause(incompatibility))
        return unsatisfied_term.subject

    def _sort_incompatibility_terms_by_most_recently_satisfied(
        self, incompatibility: Incompatibility
    ) -> list[tuple[Term, Assignment | None]]:
        """Returns a list of (VersionConstraint, Assignment) tuples sorted by the order the Assignments were made."""
        return sorted(((term, self._solution.satisfier(term)) for term in incompatibility.terms), key=lambda x: x[1])  # type: ignore[return-value,arg-type]

    def _previous_decision_level(self, sorted_terms: list[tuple[Term, Assignment | None]]) -> int:
        """Returns the decision level at which the second most recent term was satisfied."""
        most_recent_term, most_recent_satisfier = sorted_terms[-1]
        previous_satisfier_decision_level = 1
        if len(sorted_terms) > 1:
            _, previous_satisfier = sorted_terms[-2]
            previous_satisfier_decision_level = previous_satisfier.decision_level  # type: ignore
        difference = most_recent_satisfier.term.difference(most_recent_term)  # type: ignore
        if difference is None:
            return previous_satisfier_decision_level
        # If most_recent_term was only partially satisfied by the most recent satisfier, then the previous decision level
        # might be the decision level of the assignment that satisfies the difference.
        partial_satisfier = self._solution.satisfier(difference.inverse())
        return max(previous_satisfier_decision_level, partial_satisfier.decision_level)  # type: ignore

    def _merge_terms(self, terms: list[Term]) -> Iterable[Term]:
        """Returns a new list of terms where terms with the same subject are merged."""
        terms_by_subject: dict[str, Term] = {}
        for term in terms:
            subject = term.subject
            old_term = terms_by_subject.get(subject)
            if old_term is None:
                terms_by_subject[subject] = term
            else:
                new_term = old_term.intersect(term)
                if new_term is None:
                    raise ValueError(f"BUG: Mutually exclusive terms in incompatibility: {old_term}, {term}")
                terms_by_subject[subject] = new_term
        return terms_by_subject.values()

    def _create_incompatibility_from_conflict(
        self, incompatibility: Incompatibility, most_recent_term: Term, most_recent_satisfier: Assignment
    ) -> Incompatibility:
        """Create a new incompatibility combining incompatibility and the cause of the most_recent_satisfier.

        Doing this iteratively constructs an incompatibility that is guaranteed to be true - that is, we know for sure no
        solution will satisfy the incompatibility, while also approximating the intuitive notion of the root cause of the
        conflict.
        """
        terms_from_incompatibility = [term for term in incompatibility.terms if term != most_recent_term]
        terms_from_satisfier = [
            term
            for term in most_recent_satisfier.cause.incompatibility.terms  # type: ignore
            if term.subject != most_recent_satisfier.subject
        ]
        new_terms = terms_from_incompatibility + terms_from_satisfier
        # The most_recent_satisfier may not satisfy most_recent_term on its own if there are a collection of constraints on
        # most_recent_term that only satisfy it together. In this case we add the inverse of the difference to the new
        # incompatibility as well.

        # Ex: If most_recent_term is (foo:1.0.2) and solution contains assignments (foo:1.0.0, foo:1.0.2) and
        # (foo:1.0.2, foo:2.0.0), then most_recent_satisfier will be (foo:1.0.2, foo:2.0.0) even though it doesn't totally
        # satisfy (foo:1.0.2) on it's own, so we add `not (foo:2.0.0)`.
        difference = most_recent_satisfier.term.difference(most_recent_term)
        if difference is not None:
            new_terms.append(difference.inverse())

        terms = self._merge_terms(new_terms)

        new_incompatibility = Incompatibility(
            terms=terms,
            cause=ConflictCause(incompatibility, most_recent_satisfier.cause.incompatibility),  # type: ignore
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"\t{most_recent_term} is{' partially' if difference else ''} satisfied by {most_recent_satisfier.term}"
                f"\n\twhich is caused by {most_recent_satisfier.cause}\n\tThus: {new_incompatibility}"
            )
        return new_incompatibility

    def _resolve_conflict(self, incompatibility: Incompatibility) -> Incompatibility:
        """Constructs a new incompatibility that encapsulates the root cause of the conflict.

        Backtracks our current solution until the new incompatibility allows propagation to deduce new assignments.
        """
        logger.debug("CONFLICT: {}", incompatibility)
        current_incompatibility = incompatibility
        while not current_incompatibility.is_failure:
            logger.debug("Resolving conflict for {}", current_incompatibility)
            sorted_terms = self._sort_incompatibility_terms_by_most_recently_satisfied(current_incompatibility)
            most_recent_term, most_recent_satisfier = sorted_terms[-1]
            previous_decision_level = self._previous_decision_level(sorted_terms)

            # If a decision was made between the most recently satisfied term and the next most recently satisfied
            # backtrack all assignments made since and add a new incompatibility representing the conflict.
            if (
                most_recent_satisfier.is_decision  # type: ignore
                or previous_decision_level < most_recent_satisfier.decision_level  # type: ignore
            ):
                logger.debug(
                    "Backtracking from decision level {} to {}", self._solution.decision_level, previous_decision_level
                )
                self._solution.backtrack(previous_decision_level)
                if current_incompatibility != incompatibility:
                    self._add_incompatibility(current_incompatibility)
                return current_incompatibility

            current_incompatibility = self._create_incompatibility_from_conflict(
                current_incompatibility, most_recent_term, most_recent_satisfier  # type: ignore
            )
        logger.info(f"Resolution failed: {current_incompatibility}")
        self.failure = current_incompatibility
        raise ResolutionError(f"Could not resolve conflict for {incompatibility}", failure=current_incompatibility)

    def _is_conflict(self, incompatibility: Incompatibility) -> bool:
        """Checks an incompatibility against solution and returns True if there is a conflict."""
        all_terms_satisfied = True
        all_terms_refer_to_same_subject = True
        subject = None
        for term in incompatibility.terms:
            if not self._solution.satisfies(term):
                all_terms_satisfied = False
            if subject is None:
                subject = term.subject
            if term.subject != subject:
                all_terms_refer_to_same_subject = False
        return all_terms_satisfied or all_terms_refer_to_same_subject

    def _choose_package_version(self) -> str | None:
        """Tries to select a version of a required package.

        Returns the name of the next package whose incompatibilities should be propagated or `None` - indicating
        version solving is complete and a solution has been found.
        """
        unsatisfied = self._solution.unsatisfied
        if not unsatisfied:
            logger.debug("No remaining undecided packages. Resolution complete.")
            return None

        # Check if we can add incompatibilities without making a version decision.
        package_name, valid_versions = self._config.best_package(unsatisfied)
        incompatibility = self._config.incompatibilities_for_package(package_name)
        if incompatibility:
            self._add_incompatibility(incompatibility)
            return package_name
        if not valid_versions:
            # Either all versions of this package are excluded by config and version_constraint
            # or the package does not exist and therefore has no versions.
            unsatisfied_constraint = unsatisfied[package_name]
            all_versions = self._config.all_versions(package_name)
            self._add_incompatibility(
                Incompatibility(
                    terms=[
                        VersionConstraint.require(
                            package_name=package_name,
                            versions=unsatisfied_constraint.versions,  # type: ignore
                            all_versions=all_versions,
                        )
                    ],
                    cause=NoVersionsCause()
                    if all_versions
                    else PackageNotFoundCause(self._config.exceptions_for(package_name)),
                )
            )
            return package_name

        package_version = self._config.best_version_for_package(package_name, valid_versions)
        if logger.isEnabledFor(logging.DEBUG):
            valid_versions_str = ", ".join(str(version) for version in valid_versions)
            logger.debug(f"Chose {package_version} from {len(valid_versions)} valid versions: {valid_versions_str}")
        incompatibilities = self._config.incompatibilities_for(package_version=package_version)
        conflict = False
        # Add all new incompatibilities and check for conflicts.
        for incompatibility in incompatibilities:
            self._add_incompatibility(incompatibility)
            conflict = conflict or self._is_conflict(incompatibility)
        # If there is no conflict, add a decision to solution.
        if not conflict and package_version is not None:
            term = VersionConstraint(
                package_name=package_name,
                versions={package_version},
                is_positive=True,
                all_versions=self._config.all_versions(package_name),
            )
            self._solution.decide(term)
        return package_name

    def result(self) -> list[PackageVersion]:
        return self._solution.decisions

    @property
    def result_graph(self) -> ResultGraph:
        result = {package_version.subject: package_version for package_version in self._solution.decisions}
        result_dependency_graph = {}
        for package_version in self._solution.decisions:
            dep_graph = sorted(result[dep] for dep in self._config._graph.dependencies_for(package_version).keys())
            result_dependency_graph[package_version] = dep_graph
        result_graph = ResultGraph(
            direct_dependencies={package: result[package] for package in self._config.dependencies.keys()},
            dependency_graph=result_dependency_graph,
        )
        return result_graph

    def get_result(self) -> str:
        return self.result_graph.get_result_text()

    def get_dependency_edges_for_result(self) -> list[tuple[str, str]]:
        """Returns a tuple of (source, target) representing the edges between packages in the resolve result."""
        edges = []
        for package_version in self._solution.decisions:
            for package_name in self._config._graph.dependencies_for(package_version).keys():
                edges.append((package_version.subject, package_name))
        return edges
