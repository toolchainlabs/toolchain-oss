# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import functools

import pytest

from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.graph import PackageNotFoundError
from toolchain.satresolver.package import ROOT
from toolchain.satresolver.term import RootConstraint
from toolchain.satresolver.test_helpers.core_test_data import Groups, Packages, PackageVersions


# Make the RootConstraint greater than all PackageVersions.
def _cmp(x, y):
    if x == RootConstraint:
        return 1
    elif y == RootConstraint:
        return -1
    else:
        return 0 if x == y else -1 if x < y else 1


class TestGraph:
    def test_build_transitive_dependency_map(self):
        root_deps = {Packages.AA: [PackageVersions.AA_100, PackageVersions.AA_200]}
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [PackageVersions.AC_100, PackageVersions.AC_200],
                PackageVersions.AA_200: [PackageVersions.AB_100, PackageVersions.AB_200],
                PackageVersions.AA_300: [PackageVersions.BA_100],
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: []},
            Packages.AC: {PackageVersions.AC_100: [PackageVersions.BA_100]},
            Packages.BA: {
                PackageVersions.BA_100: [PackageVersions.BB_100, PackageVersions.AB_100],
                PackageVersions.BA_200: [],
            },
            Packages.BB: {PackageVersions.BB_100: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        graph.build_transitive_dependency_map(root_deps)
        assert sorted(graph._dependency_map.keys(), key=functools.cmp_to_key(_cmp)) == [
            ROOT,
            PackageVersions.AA_100,
            PackageVersions.AA_200,
            PackageVersions.AA_300,
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AC_100,
            PackageVersions.BA_100,
            PackageVersions.BA_200,
            PackageVersions.BB_100,
        ]
        assert graph._dependency_map[PackageVersions.BA_100] == {
            Packages.BB: {PackageVersions.BB_100},
            Packages.AB: {PackageVersions.AB_100},
        }
        assert graph._dependency_map[ROOT] == root_deps

    def test_all_versions(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            }
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        graph.build_transitive_dependency_map({})
        assert graph.all_versions(Packages.AA) == Groups.AA_ALL
        assert graph.all_versions(Packages.AB) == set()
        assert isinstance(graph._exceptions[Packages.AB], PackageNotFoundError)

    def test_dependencies_for(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [PackageVersions.AC_100, PackageVersions.AC_200]},
            Packages.AB: {PackageVersions.AB_100: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        graph.build_transitive_dependency_map({})
        assert graph.dependencies_for(PackageVersions.AA_100) == {
            Packages.AC: {PackageVersions.AC_100, PackageVersions.AC_200}
        }
        assert graph.dependencies_for(PackageVersions.AB_100) == {}
        assert graph.dependencies_for(PackageVersions.BB_100) == {}
        assert graph._known_invalid_versions[Packages.BB] == {PackageVersions.BB_100}

    def test_fetch_all_versions_for(self):
        # This is testing the DictGraph method, but I'm leaving it in as an example for other graph implementations.
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            }
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        graph.build_transitive_dependency_map({})
        assert graph.fetch_all_versions_for(Packages.AA) == Groups.AA_ALL
        with pytest.raises(PackageNotFoundError, match="Package a:b not found") as error_info:
            graph.fetch_all_versions_for(Packages.AB)
        assert error_info.value.to_dict() == {"msg": "Package a:b not found", "package_name": "a:b"}

    def test_fetch_dependencies_for(self):
        # This is testing the DictGraph method, but I'm leaving it in as an example for other graph implementations.
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [PackageVersions.BA_100]},
            Packages.BA: {PackageVersions.BA_100: []},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        graph.build_transitive_dependency_map({})
        assert graph.fetch_dependencies_for(PackageVersions.AA_100) == {Packages.BA: {PackageVersions.BA_100}}
        with pytest.raises(PackageNotFoundError, match="Package b:b not found") as error_info:
            graph.fetch_dependencies_for(PackageVersions.BB_100)
        assert error_info.value.to_dict() == {"msg": "Package b:b not found", "package_name": "b:b"}
