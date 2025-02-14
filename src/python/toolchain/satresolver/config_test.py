# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.satresolver.cause import DependencyCause, OverrideCause, UseLatestCause, UseLockedCause
from toolchain.satresolver.config import Config
from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.graph import PackageNotFoundError
from toolchain.satresolver.package import ROOT
from toolchain.satresolver.test_helpers.core_test_data import Groups, Packages, PackageVersions, Terms


class TestConfig:
    def test_should_use_latest(self):
        graph = DictGraph(transitive_dependency_map={})
        config = Config(dependencies={}, graph=graph, use_latest={Packages.AA, Packages.BB})
        assert config._should_use_latest == {Packages.AA, Packages.BB}
        config._have_used_latest.add(Packages.AA)
        assert config._should_use_latest == {Packages.BB}

    def test_should_use_locked(self):
        graph = DictGraph(transitive_dependency_map={})
        config = Config(
            dependencies={},
            graph=graph,
            locked={Packages.AB: PackageVersions.AB_100, Packages.BB: PackageVersions.BB_100},
        )
        assert config._should_use_locked == {Packages.AB, Packages.BB}
        config._have_used_locked.add(Packages.AB)
        assert config._should_use_locked == {Packages.BB}

    def test_all_versions(self):
        graph = DictGraph(
            transitive_dependency_map={
                Packages.AA: {
                    PackageVersions.AA_100: [],
                    PackageVersions.AA_200: [],
                    PackageVersions.AA_300: [],
                    PackageVersions.AA_400: [],
                }
            }
        )
        config = Config(dependencies={}, graph=graph)
        assert config.all_versions(Packages.AA) == Groups.AA_ALL

    def test_latest_version(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            }
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies={}, graph=graph)
        assert config._latest_version(Packages.AA) == PackageVersions.AA_400

    def test_exceptions_for(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [PackageVersions.BB_100],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            }
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies={Packages.AA: [PackageVersions.AA_100]}, graph=graph)
        assert isinstance(config.exceptions_for(Packages.BB), PackageNotFoundError)

    def test_root_incompatibilities(self):
        root_deps = {Packages.AA: [PackageVersions.AA_100]}
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [PackageVersions.AB_100],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies=root_deps, graph=graph)
        root_incompatibilities = list(config.incompatibilities_for(ROOT))
        assert len(root_incompatibilities) == 1
        root_incompatibility = root_incompatibilities[0]
        assert isinstance(root_incompatibility.cause, DependencyCause)
        assert root_incompatibility.terms[0] == Terms.TERM_ROOT
        assert root_incompatibility.terms[1] == Terms.TERM_NOT_AA_100

        # Try to fetch a second time to check we short circuit.
        assert not list(config.incompatibilities_for(ROOT))

    def test_root_incompatibilities_with_override(self):
        root_deps = {Packages.AA: [PackageVersions.AA_100]}
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            }
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies=root_deps, graph=graph, overrides={Packages.AA: [PackageVersions.AA_200]})
        root_incompatibilities = list(config.incompatibilities_for(ROOT))
        assert isinstance(root_incompatibilities[0].cause, OverrideCause)
        assert root_incompatibilities[0].terms[1] == Terms.TERM_NOT_AA_200

    def test_incompatibilities_for(self):
        root_deps = {Packages.AA: [PackageVersions.AA_100]}
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [PackageVersions.AB_100],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies=root_deps, graph=graph)
        incompatibilities = list(config.incompatibilities_for(PackageVersions.AA_100))
        assert len(incompatibilities) == 1
        assert isinstance(incompatibilities[0].cause, DependencyCause)
        assert incompatibilities[0].terms[0] == Terms.TERM_AA_100
        assert incompatibilities[0].terms[1] == Terms.TERM_NOT_AB_100

        # Try to fetch a second time to check we short circuit.
        assert not list(config.incompatibilities_for(PackageVersions.AA_100))

    def test_dependency_incompatibilities(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [PackageVersions.AB_100],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies={}, graph=graph)
        incompatibilities = list(config._dependency_incompatibilities(PackageVersions.AA_100, Terms.TERM_AA_100))
        assert len(incompatibilities) == 1
        incompatibility = incompatibilities[0]
        assert isinstance(incompatibility.cause, DependencyCause)
        assert incompatibility.terms[0] == Terms.TERM_AA_100
        assert incompatibility.terms[1] == Terms.TERM_NOT_AB_100

    def test_incompatibilities_for_package(self):
        dependency_map = {Packages.AA: {PackageVersions.AA_100: []}, Packages.AB: {PackageVersions.AB_100: []}}
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(
            dependencies={}, graph=graph, use_latest={Packages.AA}, locked={Packages.AB: PackageVersions.AB_100}
        )
        assert isinstance(config.incompatibilities_for_package(Packages.AA).cause, UseLatestCause)
        assert isinstance(config.incompatibilities_for_package(Packages.AB).cause, UseLockedCause)

    def test_best_package(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
            Packages.AC: {PackageVersions.AC_100: [], PackageVersions.AC_200: []},
        }
        unsatisfied = {Packages.AA: Terms.TERM_AA_ALL, Packages.AB: Terms.TERM_AB_ALL, Packages.AC: Terms.TERM_AC_ALL}
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(
            dependencies={}, graph=graph, use_latest={Packages.AA}, locked={Packages.AB: PackageVersions.AB_100}
        )
        assert config.best_package(unsatisfied=unsatisfied) == (Packages.AA, Groups.AA_ALL)
        config._have_used_latest.add(Packages.AA)
        assert config.best_package(unsatisfied=unsatisfied) == (Packages.AB, Groups.AB_ALL)
        config._have_used_locked.add(Packages.AB)
        assert config.best_package(unsatisfied=unsatisfied) == (
            Packages.AC,
            {PackageVersions.AC_100, PackageVersions.AC_200},
        )

    def test_valid_versions(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            }
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies={}, graph=graph)

        assert config._valid_versions_for_package(Packages.AA, Terms.TERM_AA_ALL) == Groups.AA_ALL
        assert config._valid_versions_for_package(Packages.AA, Terms.TERM_AA_12) == {
            PackageVersions.AA_100,
            PackageVersions.AA_200,
        }
        graph._known_invalid_versions[Packages.AA].add(PackageVersions.AA_400)
        assert config._valid_versions_for_package(Packages.AA, Terms.TERM_AA_ALL) == {
            PackageVersions.AA_100,
            PackageVersions.AA_200,
            PackageVersions.AA_300,
        }
        assert config._valid_versions_for_package(Packages.AA, Terms.TERM_AA_34) == {PackageVersions.AA_300}

    def test_best_version_for_package(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: []},
            Packages.AC: {PackageVersions.AC_100: [], PackageVersions.AC_200: []},
            Packages.BA: {PackageVersions.BA_100: [], PackageVersions.BA_200: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(
            dependencies={},
            graph=graph,
            locked={Packages.AB: PackageVersions.AB_100},
            use_latest={Packages.AC},
            downgrades={Packages.BA},
        )
        assert (
            config.best_version_for_package(package_name=Packages.AA, valid_versions=Groups.AA_ALL)
            == PackageVersions.AA_400
        )
        assert (
            config.best_version_for_package(
                package_name=Packages.AA, valid_versions={PackageVersions.AA_100, PackageVersions.AA_200}
            )
            == PackageVersions.AA_200
        )
        assert (
            config.best_version_for_package(package_name=Packages.AB, valid_versions=Groups.AB_ALL)
            == PackageVersions.AB_100
        )
        assert (
            config.best_version_for_package(package_name=Packages.AC, valid_versions=Groups.AC_ALL)
            == PackageVersions.AC_300
        )
        assert (
            config.best_version_for_package(package_name=Packages.BA, valid_versions=Groups.BA_ALL)
            == PackageVersions.BA_100
        )
        # Real package, no valid versions.
        with pytest.raises(ToolchainAssertion, match="No valid version passed"):
            config.best_version_for_package(Packages.AA, {})

        # Fake package, no versions.
        with pytest.raises(ToolchainAssertion, match="No valid version passed"):
            config.best_version_for_package(Packages.BC, {})
