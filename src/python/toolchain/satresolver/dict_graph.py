# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from toolchain.satresolver.graph import Graph, PackageNotFoundError
from toolchain.satresolver.package import PackageVersion


class DictGraph(Graph):
    """Construct a graph from a dictionary of dependencies.

    For use in testing.
    """

    def __init__(self, transitive_dependency_map: dict[str, dict[PackageVersion, Iterable[PackageVersion]]]):
        self._transitive_dependency_map = transitive_dependency_map
        super().__init__()

    def fetch_all_versions_for(self, package_name: str) -> set[PackageVersion]:
        """Returns all versions of this package as a set of PackageVersions."""
        versions = self._transitive_dependency_map.get(package_name)
        if versions is None:
            raise PackageNotFoundError(f"Package {package_name} not found", package_name)
        return set(versions.keys())

    def fetch_dependencies_for(self, package_version: PackageVersion) -> dict[str, set[PackageVersion]]:
        """Return a dictionary of the dependencies of package_version as package_name:

        set(PackageVersions)
        """
        dependencies: defaultdict = defaultdict(set)
        package = self._transitive_dependency_map.get(package_version.subject)
        if package is None:
            raise PackageNotFoundError(f"Package {package_version.subject} not found", package_version.subject)
        deps = package.get(package_version)
        if deps is None:
            raise PackageNotFoundError(f"Package version {package_version} not found", package_version.subject)
        for dep in deps:
            dependencies[dep.package_name].add(dep)
        return dependencies

    def dependencies_for_root(self, requirements):
        return requirements
