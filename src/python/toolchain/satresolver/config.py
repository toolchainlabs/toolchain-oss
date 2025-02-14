# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from collections.abc import Iterable, Iterator
from typing import Optional

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.satresolver.cause import DependencyCause, OverrideCause, UseLatestCause, UseLockedCause
from toolchain.satresolver.graph import Graph
from toolchain.satresolver.incompatibility import Incompatibility
from toolchain.satresolver.package import ROOT, PackageVersion
from toolchain.satresolver.term import RootConstraint, Term, VersionConstraint

logger = logging.getLogger(__name__)


class Config:
    def __init__(
        self,
        dependencies: dict[str, Iterable[PackageVersion]],
        graph: Graph,
        use_latest: Optional[set[str]] = None,
        locked: Optional[dict[str, PackageVersion]] = None,
        downgrades: Optional[set[str]] = None,
        overrides: Optional[dict[str, list[PackageVersion]]] = None,
    ):
        self.dependencies = dependencies
        self._use_latest = use_latest or set()
        self._locked = locked or {}
        self._downgrades = downgrades or set()
        self.overrides = overrides or {}
        self._graph = graph
        self._have_listed_incompatibilities: set[PackageVersion] = set()
        self._have_used_latest: set[str] = set()
        self._have_used_locked: set[str] = set()
        self._graph.build_transitive_dependency_map(dependencies)

    @property
    def _should_use_latest(self) -> set[str]:
        """Returns a set of package_names for which we should use latest."""
        return self._use_latest - self._have_used_latest

    @property
    def _should_use_locked(self) -> set[str]:
        """Returns a set of package_names for which we should use a locked version."""
        return set(self._locked.keys()) - self._have_used_locked

    def all_versions(self, package_name: str) -> list[PackageVersion]:
        """Returns all versions of this package as a set of PackageVersions."""
        return self._graph.all_versions(package_name)

    def dependencies_for(self, package_version: PackageVersion) -> dict:
        return self._graph.dependencies_for(package_version)

    def _latest_version(self, package_name: str):
        """Returns the latest PackageVersion for package_name."""
        return max(self._graph.all_versions(package_name))

    def root_incompatibilities(self) -> Iterator[Incompatibility]:
        return self.incompatibilities_for(ROOT)

    def exceptions_for(self, subject: str) -> Exception:
        return self._graph.exceptions_for(subject)

    def incompatibilities_for(self, package_version: PackageVersion) -> Iterator[Incompatibility]:
        """Constructs a list of Incompatibilities for a PackageVersion from its dependency data."""
        if package_version in self._have_listed_incompatibilities:
            logger.debug(f"Already listed incompatibilities for {package_version}")
            return
        if package_version == ROOT:
            dependee_term = RootConstraint.require()
        else:
            all_versions = self._graph.all_versions(package_version.subject)
            dependee_term = VersionConstraint.require(
                package_name=package_version.subject, versions={package_version}, all_versions=all_versions
            )
        self._have_listed_incompatibilities.add(package_version)
        yield from self._dependency_incompatibilities(package_version, dependee_term)

    def _dependency_incompatibilities(
        self, package_version: PackageVersion, dependee_term: Term
    ) -> Iterator[Incompatibility]:
        dependencies = self.dependencies_for(package_version)
        for package_name, versions in dependencies.items():
            if package_name in self.overrides:
                pinned_versions = self.overrides[package_name]
                logger.debug("{} depends on {}. Overriding with {}", package_name, versions, pinned_versions)
                versions = pinned_versions
            dependency_term = VersionConstraint.exclude(
                package_name=package_name, versions=set(versions), all_versions=self._graph.all_versions(package_name)
            )
            yield Incompatibility(
                cause=OverrideCause() if package_name in self.overrides else DependencyCause(),
                terms=[dependee_term, dependency_term],
            )

    def incompatibilities_for_package(self, package_name: str) -> Optional[Incompatibility]:
        """Checks for incompatibilities we can add to a package before choosing a specific version.

        This is where configuration for `locked` or `use_latest` are applied.
        """
        all_versions = self._graph.all_versions(package_name)
        if package_name in self._should_use_latest:
            logger.debug(f"Using latest for {package_name}")
            self._have_used_latest.add(package_name)
            return Incompatibility(
                cause=UseLatestCause(),
                terms=[
                    VersionConstraint.require(
                        package_name=package_name,
                        versions={self._latest_version(package_name)},
                        all_versions=all_versions,
                    )
                ],
            )

        if package_name in self._should_use_locked:
            logger.debug(f"Using locked for {package_name}")
            self._have_used_locked.add(package_name)
            return Incompatibility(
                cause=UseLockedCause(),
                terms=[
                    VersionConstraint.require(
                        package_name=package_name, versions={self._locked[package_name]}, all_versions=all_versions
                    )
                ],
            )
        return None

    def best_package(self, unsatisfied: dict[str, Term]) -> tuple[str, set[PackageVersion]]:
        """Returns the most constrained package, and the set of its valid versions.

        Packages with multiple valid versions and `use_latest` or `locked` configured are sorted as though they have
        only a single valid version, but return the set of all valid versions.
        """
        valid_versions_for_packages = {
            package_name: self._valid_versions_for_package(package_name, constraint)
            for package_name, constraint in unsatisfied.items()
        }
        packages_with_extra_constraints = self._should_use_locked.union(self._should_use_latest)

        def num_valid_versions(package_name: str) -> int:
            if package_name in packages_with_extra_constraints:
                return 1
            return len(valid_versions_for_packages[package_name])

        # Tuples sort first by the first element (number of valid versions), and then tie break by the lexical sort
        # of the package_name. This is desirable to make sure the best package is deterministic.
        packages_sorted_by_num_valid_versions = sorted(
            (num_valid_versions(package_name), package_name) for package_name in valid_versions_for_packages
        )
        _, best_package = packages_sorted_by_num_valid_versions[0]
        valid_versions_for_package = valid_versions_for_packages[best_package]
        return best_package, valid_versions_for_package

    def _valid_versions_for_package(self, package_name: str, version_constraint: Term) -> set[PackageVersion]:
        """Returns a set of PackageVersions which are not known to be invalid and which satisfy the
        version_constraint."""
        if not isinstance(version_constraint, VersionConstraint):
            raise ToolchainAssertion(f"Unexpected type of version_constraint {type(version_constraint)}")
        versions = version_constraint.versions
        if package_name not in self._graph._known_invalid_versions:
            for package_version in versions:
                # We call it here because it will populate self._graph._known_invalid_versions if needed
                self.dependencies_for(package_version)
        possible_versions = self._graph.all_versions(package_name) - self._graph._known_invalid_versions[package_name]
        return possible_versions.intersection(versions)

    def best_version_for_package(self, package_name: str, valid_versions: set[PackageVersion]) -> PackageVersion:
        """Returns a PackageVersion which satisfies the version constraint or None if there is no such version.

        This is our guess at which version is "best". By default, this picks the most recent valid version.
        """
        if not valid_versions:
            raise ToolchainAssertion("No valid version passed")
        locked_version = self._locked.get(package_name)
        if locked_version is not None and locked_version in valid_versions:
            return locked_version
        if package_name in self._downgrades:
            return min(valid_versions)
        return max(valid_versions)

    def __str__(self) -> str:
        reqs = ", ".join(str(req) for req in self.dependencies)
        return f"{type(self).__name__} ({self._graph}) reqs=[{reqs}]"
