# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.packagerepo.maven.coordinates import GACoordinates, GAVCoordinates
from toolchain.packagerepo.maven.models import MavenArtifact, MavenArtifactVersion, MavenDependency
from toolchain.packagerepo.maven.version.maven_semantic_version import MavenSemver
from toolchain.satresolver.config import Config
from toolchain.satresolver.core import Resolver
from toolchain.satresolver.graph import PackageNotFoundError, VersionNotFoundError
from toolchain.satresolver.maven.maven_graph import MavenGraph
from toolchain.satresolver.package import PackageVersion

AA = "a:a"
AB = "a:b"
AC = "a:c"
BB = "b:b"
BC = "b:c"

AA_100 = PackageVersion(AA, MavenSemver("1.0.0"))
AA_200 = PackageVersion(AA, MavenSemver("2.0.0"))
AA_300 = PackageVersion(AA, MavenSemver("3.0.0"))
AB_100 = PackageVersion(AB, MavenSemver("1.0.0-fake"))
AC_100 = PackageVersion(AC, MavenSemver("1.0.0"))
AC_200 = PackageVersion(AC, MavenSemver("2.0.0"))
AC_300 = PackageVersion(AC, MavenSemver("3.0.0"))

BB_100 = PackageVersion(BB, MavenSemver("1.0.0"))
BB_200 = PackageVersion(BB, MavenSemver("2.0.0"))
BB_300 = PackageVersion(BB, MavenSemver("3.0.0"))


def get_maven_artifact_from_package_name(package_name):
    group_id, artifact_id = package_name.split(":")
    return MavenArtifact.for_coordinates(GACoordinates(group_id=group_id, artifact_id=artifact_id))


def get_maven_artifact_version_from_package_version(package_version):
    group_id, artifact_id = package_version.package_name.split(":")
    return MavenArtifactVersion.for_coordinates(
        GAVCoordinates(group_id=group_id, artifact_id=artifact_id, version=package_version.version)
    )


@pytest.mark.django_db()
class TestMavenGraph:
    @pytest.fixture(autouse=True)
    def _dependencies(self):
        ma_aa = get_maven_artifact_from_package_name(AA)
        ma_ab = get_maven_artifact_from_package_name(AB)
        get_maven_artifact_from_package_name(AC)
        ma_bb = get_maven_artifact_from_package_name(BB)
        get_maven_artifact_version_from_package_version(AA_100)
        get_maven_artifact_version_from_package_version(AA_200)
        mav_aa_300 = get_maven_artifact_version_from_package_version(AA_300)
        mav_ac_100 = get_maven_artifact_version_from_package_version(AC_100)
        mav_ac_200 = get_maven_artifact_version_from_package_version(AC_200)
        mav_ac_300 = get_maven_artifact_version_from_package_version(AC_300)
        mav_bb_100 = get_maven_artifact_version_from_package_version(BB_100)
        mav_bb_200 = get_maven_artifact_version_from_package_version(BB_200)
        mav_bb_300 = get_maven_artifact_version_from_package_version(BB_300)

        deps = [
            (mav_bb_100, ma_aa, "[1.0.0]", "compile"),
            (mav_bb_200, ma_aa, "[1.0.0,2.0.0]", "compile"),
            (mav_ac_100, ma_aa, "[1.0.0,2.0.0]", "compile"),
            (mav_ac_200, ma_aa, "[1.0.0]", "runtime"),  # Scope
            (mav_ac_200, ma_bb, "[,3.0.0)", "compile"),
            (mav_ac_300, ma_bb, "1.0.0", "compile"),  # Soft Requirement
            (mav_aa_300, ma_ab, "[1.0.0]", "compile"),  # Bad dep - package has no versions
            (mav_bb_300, ma_aa, "[,1.0.0)", "compile"),  # Bad dep - version spec excludes all versions
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

    def test_fetch_all_versions_for(self):
        graph = MavenGraph()
        graph.build_transitive_dependency_map({AA: [AA_100]})
        assert graph.fetch_all_versions_for(AA) == {AA_100, AA_200, AA_300}
        with pytest.raises(PackageNotFoundError, match="b:c could not be found") as error_info:
            graph.fetch_all_versions_for(BC)
        assert error_info.value.to_dict() == {"msg": "b:c could not be found", "package_name": "b:c"}

    def test_dependencies_for_scopes(self):
        graph = MavenGraph()
        graph.build_transitive_dependency_map(dependencies={AC: [AC_200, AC_300]})
        assert graph.dependencies_for_scopes(AC_300, {"compile"}) == {BB: {BB_100, BB_200, BB_300}}
        assert graph.dependencies_for_scopes(AC_200, {"compile", "runtime"}) == {BB: {BB_100, BB_200}, AA: {AA_100}}

    def test_fetch_dependencies_for(self):
        graph = MavenGraph()
        graph.build_transitive_dependency_map(dependencies={AA: [AA_100]})
        assert not graph.fetch_dependencies_for(AA_100)
        assert graph.fetch_dependencies_for(BB_200) == {AA: {AA_100, AA_200}}
        assert graph.fetch_dependencies_for(AC_300) == {BB: {BB_100, BB_200, BB_300}}
        assert graph.fetch_dependencies_for(AC_200) == {BB: {BB_100, BB_200}, AA: {AA_100}}
        with pytest.raises(
            VersionNotFoundError, match="a:a:3.0.0 depends on a:b which has no versions which satisfy spec"
        ) as error_info:
            graph.fetch_dependencies_for(AA_300)
        assert error_info.value.to_dict() == {
            "available_versions": [],
            "msg": "a:a:3.0.0 depends on a:b which has no versions which satisfy spec '[1.0.0]'",
            "package_name": "a:b",
        }
        with pytest.raises(
            VersionNotFoundError, match="b:b:3.0.0 depends on a:a which has no versions which satisfy spec"
        ) as error_info:
            graph.fetch_dependencies_for(BB_300)
        assert error_info.value.to_dict() == {
            "available_versions": ["1.0.0", "2.0.0", "3.0.0"],
            "msg": "b:b:3.0.0 depends on a:a which has no versions which satisfy spec '[,1.0.0)'",
            "package_name": "a:a",
        }

    def test_resolve(self):
        config = Config(dependencies={AA: [AA_100]}, graph=MavenGraph())
        resolver = Resolver(config)
        resolver.run()
