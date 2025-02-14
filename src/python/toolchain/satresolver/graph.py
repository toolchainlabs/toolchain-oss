# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict
from functools import lru_cache

from toolchain.base.toolchain_error import ToolchainError
from toolchain.satresolver.package import ROOT, PackageVersion

logger = logging.getLogger(__name__)

DependencyMap = dict[PackageVersion, dict]


class PackageError(ToolchainError):
    def __init__(self, msg: str, package_name: str):
        super().__init__(msg)
        self._package_name = package_name

    @property
    def package_name(self) -> str:
        return self._package_name

    def to_dict(self) -> dict:
        return {"msg": str(self), "package_name": self.package_name}


class InvalidRequirementsError(ToolchainError):
    """Raised when we can't parse requirements string(s)"""

    def __init__(self, requirement_string: str, parse_error: Exception):
        super().__init__(f'Could not parse requirement "{requirement_string.lower()}"')
        self._requirement_string = requirement_string
        self._parse_error = parse_error

    @property
    def parse_error(self) -> Exception:
        return self._parse_error

    def to_dict(self) -> dict:
        return {"msg": str(self), "package_name": self._requirement_string, "parse_error": str(self.parse_error)}


class PackageNotFoundError(PackageError):
    """Raised when a package could not be found."""


class VersionNotFoundError(PackageNotFoundError):
    """A version of a package could not be found."""

    def __init__(self, msg, project_name: str, available_versions: list[str]):
        super().__init__(msg, project_name)
        self._available_versions = available_versions

    @property
    def available_versions(self) -> list[str]:
        return self._available_versions

    def to_dict(self) -> dict:
        error_dict = super().to_dict()
        error_dict["available_versions"] = self.available_versions
        return error_dict


class Graph:
    """Base implementation of dependency graph for use in resolving dependencies.

    The interface should be entirely in terms of PackageVersions, though subclasses can implement the
    `fetch_dependencies_for` and `fetch_all_versions_for` methods in which ever terms make sense.

    TODO: The sentence above does not represent a coherent API... We should figure out an actual type hierarchy
    that makes sense.
    """

    def __init__(self) -> None:
        self._dependency_map: DependencyMap = {}
        self._known_invalid_versions: dict[str, set[PackageVersion]] = defaultdict(set)
        # Used only by resolve_graph_to_json. TODO: find another way to make that work.
        self._packages: dict[str, PackageVersion] = {}
        self._exceptions: dict[PackageVersion | str, PackageError] = {}

    def build_transitive_dependency_map(self, dependencies) -> None:
        """Builds the transitive dependency map from the root dependencies."""
        direct_dependencies = self.dependencies_for_root(dependencies)
        visited = set()
        to_visit = list(direct_dependencies.keys())
        while to_visit:
            package_name = to_visit.pop()
            for version in self.all_versions(package_name):
                package_names = self.dependencies_for(version).keys()
                to_visit.extend(package for package in package_names if package not in visited)
            visited.add(package_name)
        self._dependency_map[ROOT] = direct_dependencies

    @lru_cache(maxsize=None)
    def all_versions(self, package_name: str):
        """Returns all versions of this package as a set of PackageVersions."""
        try:
            packages = self.fetch_all_versions_for(package_name)
            self._packages[package_name] = packages
            return packages
        except PackageNotFoundError as e:
            self._exceptions[package_name] = e
            return set()

    def fetch_all_versions_for(self, package_name: str):
        """Returns all versions of this package as a set of PackageVersions.

        If the package does not exist, raises PackageNotFoundError
        """
        raise NotImplementedError

    def dependencies_for(self, package_version) -> dict:
        """Returns the dependencies of package_version as a dictionary of package_name : set(PackageVersions).

        Uses cached dependency information if possible.
        """
        dependencies = self._dependency_map.get(package_version)
        if dependencies is None:
            try:
                dependencies = self.fetch_dependencies_for(package_version)
            except PackageNotFoundError as error:
                self._known_invalid_versions[package_version.subject].add(package_version)
                self._exceptions[package_version] = error
                dependencies = {}
            self._dependency_map[package_version] = dependencies
        return dependencies

    def dependencies_for_root(self, requirements):
        """Parses requirements from user input and returns them as a dictionary of package_name: set(PackageVersions)

        If package version does not exist, raises PackageNotFoundError.
        """
        raise NotImplementedError

    def fetch_dependencies_for(self, package_version) -> dict:
        """Return a dictionary of the dependencies of package_version as package_name: set(PackageVersions).

        If package version does not exist, raises PackageNotFoundError.
        """
        raise NotImplementedError

    def exceptions_for(self, package_version):
        """Return exceptions for package_version or None."""
        return self._exceptions.get(package_version)
