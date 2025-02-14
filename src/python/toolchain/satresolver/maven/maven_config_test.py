# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.packagerepo.maven.coordinates import GACoordinates, GAVCoordinates
from toolchain.packagerepo.maven.models import MavenArtifact, MavenArtifactVersion, MavenDependency
from toolchain.packagerepo.maven.version.maven_semantic_version import MavenSemver
from toolchain.satresolver.maven.maven_config import MavenConfig
from toolchain.satresolver.package import PackageVersion

AA = "a:a"
AB = "a:b"
AC = "a:c"
BB = "b:b"
BC = "b:c"

AA_100 = PackageVersion(AA, MavenSemver("1.0.0"))
AA_200 = PackageVersion(AA, MavenSemver("2.0.0"))
AA_300 = PackageVersion(AA, MavenSemver("3.0.0"))
AA_400 = PackageVersion(AA, MavenSemver("4.0.0"))

AB_100 = PackageVersion(AB, MavenSemver("1.0.0"))
AB_200 = PackageVersion(AB, MavenSemver("2.0.0"))

AC_100 = PackageVersion(AC, MavenSemver("1.0.0"))
AC_200 = PackageVersion(AC, MavenSemver("2.0.0"))
AC_300 = PackageVersion(AC, MavenSemver("3.0.0"))

BB_100 = PackageVersion(BB, MavenSemver("1.0.0"))
BB_200 = PackageVersion(BB, MavenSemver("2.0.0"))
BB_300 = PackageVersion(BB, MavenSemver("3.0.0"))

AA_ALL = {AA_100, AA_200, AA_300, AA_400}
AB_ALL = {AB_100, AB_200}
AC_ALL = {AC_100, AC_200, AC_300}
BB_ALL = {BB_100, BB_200, BB_300}


def maven_artifact_from_package_name(package_name):
    group_id, artifact_id = package_name.split(":")
    return MavenArtifact.for_coordinates(GACoordinates(group_id=group_id, artifact_id=artifact_id))


def maven_artifact_version_from_package_version(package_version):
    group_id, artifact_id = package_version.package_name.split(":")
    return MavenArtifactVersion.for_coordinates(
        GAVCoordinates(group_id=group_id, artifact_id=artifact_id, version=package_version.version)
    )


@pytest.mark.django_db()
class TestMavenConfig:
    @pytest.fixture(autouse=True)
    def _maven_data(self):
        ma_aa = maven_artifact_from_package_name(AA)
        ma_ab = maven_artifact_from_package_name(AB)
        maven_artifact_from_package_name(AC)
        maven_artifact_version_from_package_version(AA_100)
        maven_artifact_version_from_package_version(AA_200)
        maven_artifact_version_from_package_version(AA_300)
        mav_ab_100 = maven_artifact_version_from_package_version(AB_100)
        mav_ab_200 = maven_artifact_version_from_package_version(AB_200)
        mav_ac_100 = maven_artifact_version_from_package_version(AC_100)
        mav_ac_200 = maven_artifact_version_from_package_version(AA_200)
        deps = [
            (mav_ab_100, ma_aa, "1.0.0", "compile"),
            (mav_ab_200, ma_aa, "[1.0.0,2.0.0]", "compile"),
            (mav_ac_100, ma_aa, "[2.0.0,3.0.0]", "compile"),
            (mav_ac_200, ma_aa, "[1.0.0]", "runtime"),
            (mav_ac_200, ma_ab, "[2.0.0,3.0.0)", "compile"),
        ]
        for dep in deps:
            MavenDependency.objects.create(
                dependent=dep[0],
                depends_on_artifact=dep[1],
                depends_on_version_spec=dep[2],
                classifier="",
                type="",
                scope=dep[3],
            )

    def test_dependencies_for(self):
        config = MavenConfig(dependencies={AB: [AB_100]}, scopes={"compile"})
        assert config.dependencies_for(AB_100) == {AA: {AA_100, AA_200, AA_300}}
        config = MavenConfig(dependencies={AB: [AB_100]}, scopes={"runtime"})
        assert config.dependencies_for(AB_100) == {}

    def test_should_use_soft_requirement(self):
        config = MavenConfig(dependencies={AB: [AB_100]}, scopes={"compile"})
        assert config._should_use_soft_requirement(current_decisions={}) == set()
        assert config._should_use_soft_requirement(current_decisions={AB_100}) == {AA}

    def test_preferred_versions(self):
        config = MavenConfig(dependencies={AB: [AB_100]}, scopes={"compile"})
        assert config._preferred_versions(AA, {AA_100, AA_200, AA_300}, current_decisions={}) == {
            AA_100,
            AA_200,
            AA_300,
        }
        assert config._preferred_versions(AA, {AA_100, AA_200, AA_300}, current_decisions={AB_100}) == {AA_100}

    def test_best_version_for_package(self):
        dependencies = {AA: [AA_100, AA_200, AA_300, AA_400], AB: [AB_100, AB_200]}
        config = MavenConfig(
            dependencies=dependencies, scopes={"compile"}, locked={AB: AB_100}, use_latest={AC}, downgrades={BB}
        )

        # Choose highest version
        assert config.best_version_for_package(package_name=AA, valid_versions=AA_ALL, current_decisions={}) == AA_400
        # Choose highest version from restricted set
        assert (
            config.best_version_for_package(package_name=AA, valid_versions={AA_100, AA_200}, current_decisions={})
            == AA_200
        )
        # Soft requirement
        assert (
            config.best_version_for_package(
                package_name=AA, valid_versions={AA_100, AA_200}, current_decisions={AB_100}
            )
            == AA_100
        )
        # Locked
        assert config.best_version_for_package(package_name=AB, valid_versions=AB_ALL, current_decisions={}) == AB_100
        # Use latest
        assert config.best_version_for_package(package_name=AC, valid_versions=AC_ALL, current_decisions={}) == AC_300
        # Downgrades
        assert config.best_version_for_package(package_name=BB, valid_versions=BB_ALL, current_decisions={}) == BB_100
        # Real package, no valid versions.
        assert config.best_version_for_package(package_name=AA, valid_versions={}, current_decisions={}) is None
        # Fake package, no versions.
        assert config.best_version_for_package(package_name=BC, valid_versions={}, current_decisions={}) is None
