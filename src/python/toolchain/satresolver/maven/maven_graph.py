# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from collections import defaultdict

from toolchain.packagerepo.maven.coordinates import GACoordinates, GAVCoordinates
from toolchain.packagerepo.maven.models import MavenArtifact, MavenArtifactVersion
from toolchain.packagerepo.maven.version.maven_semantic_version_spec import MavenVersionSpec
from toolchain.satresolver.graph import Graph, PackageNotFoundError, VersionNotFoundError
from toolchain.satresolver.package import PackageVersion
from toolchain.satresolver.term import RootConstraint

COMPILE = "compile"
PROVIDED = "provided"
RUNTIME = "runtime"
TEST = "test"
SYSTEM = "system"

SCOPES = {COMPILE, PROVIDED, RUNTIME, TEST, SYSTEM}


def package_name_to_ga_coords(package_name: str) -> GACoordinates:
    group_id, artifact_id = package_name.split(":")
    return GACoordinates(group_id, artifact_id)


def package_version_to_gav_coordinates(package_version) -> GAVCoordinates:
    group_id, artifact_id = package_version.package_name.split(":")
    version = package_version.version
    return GAVCoordinates(group_id, artifact_id, version)


def gav_coordinates_to_package_version(gav) -> PackageVersion:
    return PackageVersion(package_name=f"{gav.group_id}:{gav.artifact_id}", version=gav.MavenSemver)


def maven_artifact_version_to_package_version(mav) -> PackageVersion:
    coords = mav.coordinates()
    version = coords.MavenSemver()
    package_name = f"{coords.group_id}:{coords.artifact_id}"
    return PackageVersion(package_name, version)


def maven_artifact_from_package_name(package_name: str) -> MavenArtifact:
    coordinates = package_name_to_ga_coords(package_name)
    artifact = MavenArtifact.get_or_none(group_id=coordinates.group_id, artifact_id=coordinates.artifact_id)
    if not artifact:
        raise PackageNotFoundError(f"{package_name} could not be found", package_name)
    return artifact


def maven_artifact_version_from_package_version(package_version) -> MavenArtifactVersion:
    artifact = maven_artifact_from_package_name(package_version.package_name)
    artifact_version = MavenArtifactVersion.get_or_none(artifact=artifact, version=package_version.version)
    if not artifact_version:
        versions = MavenArtifactVersion.get_available_versions(artifact=artifact)
        raise VersionNotFoundError(f"{package_version} not found", package_version.package_name, versions)
    return artifact_version


class MavenGraph(Graph):
    def __init__(self):
        self._scoped_dependencies = {scope: defaultdict(dict) for scope in SCOPES}
        self.soft_requirements = defaultdict(dict)
        super().__init__()

    def fetch_all_versions_for(self, package_name) -> set:
        """Returns all versions of this package as a set of PackageVersions."""
        artifact = maven_artifact_from_package_name(package_name)
        maven_artifact_versions = artifact.all_versions()
        return {maven_artifact_version_to_package_version(version) for version in maven_artifact_versions}

    def dependencies_for_scopes(self, package_version, scopes) -> dict:
        if package_version == RootConstraint:
            # TODO: Do people also include scopes on their direct deps? Probably.
            return self.dependencies_for(RootConstraint)
        dependencies_for_scopes: dict = {}
        for scope in scopes:
            dependencies = self._scoped_dependencies[scope].get(package_version)
            if dependencies is not None:
                dependencies_for_scopes.update(dependencies)
        return dependencies_for_scopes

    def fetch_dependencies_for(self, package_version) -> dict:
        """Return a dictionary of the dependencies of package_version as package_name: `set(PackageVersions)`"""
        dependency_data = list(maven_artifact_version_from_package_version(package_version).dependency_data())
        dependencies = {}
        for dependency in dependency_data:
            package_name = str(dependency.depends_on_artifact.coordinates())
            all_versions = self.all_versions(package_name)
            version_spec = MavenVersionSpec(dependency.depends_on_version_spec)
            dependency_versions = {
                version for version in all_versions if version_spec.is_valid_version(version.version)
            }
            if not dependency_versions:
                raise VersionNotFoundError(
                    f"{package_version} depends on {package_name} which has no versions which satisfy spec '{version_spec}'",
                    project_name=package_name,
                    available_versions=sorted(str(ver.version) for ver in all_versions),
                )
            if version_spec.soft_requirement:
                preferred_version = PackageVersion(package_name, version_spec.soft_requirement)
                self.soft_requirements[package_name][package_version] = preferred_version
            self._scoped_dependencies[dependency.scope][package_version][package_name] = dependency_versions
            dependencies[package_name] = dependency_versions
        return dependencies

    def dependencies_for_root(self, requirements) -> dict:
        # TODO: This should be updated to parse an inputted pom file and return a map of
        # {package_name: {valid versions}}
        return requirements
