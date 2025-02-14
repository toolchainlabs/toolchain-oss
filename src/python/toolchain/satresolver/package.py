# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering

from toolchain.packagerepo.maven.version.maven_semantic_version import MavenSemver


@dataclass(frozen=True, order=True)
class PackageVersion:
    """A specific version of a package."""

    package_name: str
    version: str | MavenSemver

    @property
    def subject(self) -> str:
        return self.package_name

    def __str__(self):
        return f"{self.package_name}:{self.version}"


@total_ordering
@dataclass(frozen=True, order=False)
class Root(PackageVersion):
    """A fictional root package, representing the project we are running the resolve for."""

    @property
    def subject(self) -> str:
        return self.package_name

    def __str__(self):
        return f"{self.package_name}"

    def __lt__(self, other):
        """Root should always be the first item in a list of PackageVersions."""
        if isinstance(other, PackageVersion):
            return True
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, Root):
            return True
        return False


ROOT = Root(package_name="__ROOT__", version="")
