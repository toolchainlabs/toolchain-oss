# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from collections import defaultdict
from typing import cast

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.satresolver.config import Config
from toolchain.satresolver.maven.maven_graph import COMPILE, SCOPES, MavenGraph


class ConfigurationError(ToolchainAssertion):
    """Raised when Config is provided with invalid configuration."""


class MavenConfig(Config):
    """Configuration for resolving dependencies defined in Maven's pom file format."""

    def __init__(self, dependencies, scopes=None, use_latest=None, locked=None, downgrades=None):
        self.scopes = set(scopes) or {COMPILE}
        if not self.scopes.issubset(SCOPES):
            raise ConfigurationError(f"Scopes must be a subset of {', '.join(SCOPES)}.")
        super().__init__(
            graph=MavenGraph(), dependencies=dependencies, use_latest=use_latest, locked=locked, downgrades=downgrades
        )

    def dependencies_for(self, package_version) -> dict:
        graph = cast(MavenGraph, self._graph)
        return graph.dependencies_for_scopes(package_version, self.scopes)

    def _should_use_soft_requirement(self, current_decisions):
        """Returns a set of package_names for which we have soft requirements."""
        return {
            package_name
            for package_name, soft_requirements_for_package in self._graph.soft_requirements.items()
            if set(soft_requirements_for_package.keys()).intersection(current_decisions)
        }

    def _preferred_versions(self, package_name, valid_versions, current_decisions):
        """Returns a set of valid PackageVersions which satisfy the most soft requirements.

        Only consideres the soft requirements of packages already in our solution. If there are no valid preferred
        versions returns the set of all valid versions.
        """
        preferred_versions = defaultdict(int)
        soft_requirements_for_package = self._graph.soft_requirements[package_name]
        packages_with_preferred_versions = set(soft_requirements_for_package.keys()).intersection(current_decisions)
        dependees_with_valid_preferences = [
            package
            for package in packages_with_preferred_versions
            if soft_requirements_for_package[package] in valid_versions
        ]
        if dependees_with_valid_preferences:
            for package in dependees_with_valid_preferences:
                preferred_version = soft_requirements_for_package[package]
                preferred_versions[preferred_version] += 1
            max_dependees = max(preferred_versions.values())
            return {version for version, num_dependees in preferred_versions.items() if num_dependees == max_dependees}
        return valid_versions

    def best_version_for_package(self, package_name, valid_versions, current_decisions):
        """Returns a PackageVersion which satisfies the version constraint or None if there is no such version.

        This is our guess at which version is "best". By default, this picks the most recent valid version.
        """
        if not valid_versions:
            return None
        locked_version = self._locked.get(package_name)
        if locked_version is not None and locked_version in valid_versions:
            return locked_version
        if package_name in self._should_use_soft_requirement(current_decisions):
            valid_versions = self._preferred_versions(package_name, valid_versions, current_decisions)
        if package_name in self._downgrades:
            return min(valid_versions)
        return max(valid_versions)
