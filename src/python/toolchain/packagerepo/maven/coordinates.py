# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass

from toolchain.packagerepo.maven.version.maven_semantic_version import MavenSemver

# Useful lightweight data classes representing Maven coordinates.


@dataclass
class GACoordinates:
    """Coordinates of an unversioned artifact."""

    group_id: str
    artifact_id: str

    def __str__(self):
        return f"{self.group_id}:{self.artifact_id}"


@dataclass
class GAVCoordinates:
    """# Coordinates of a versioned artifact."""

    group_id: str
    artifact_id: str
    version: str

    def __str__(self):
        return f"{self.group_id}:{self.artifact_id}:{self.version}"

    def MavenSemver(self):
        return MavenSemver(self.version)
