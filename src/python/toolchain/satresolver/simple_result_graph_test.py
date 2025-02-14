# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.config import Config
from toolchain.satresolver.core import Resolver
from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.test_helpers.core_test_data import Packages, PackageVersions


def create_resolver(transitive_dependency_map, dependencies, locked=None, use_latest=None, downgrades=None):
    config = Config(
        dependencies=dependencies,
        graph=DictGraph(transitive_dependency_map),
        use_latest=use_latest,
        locked=locked,
        downgrades=downgrades,
    )
    return Resolver(config)


class TestResultGraph:
    def test_simple_dependency_tree(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_200: [PackageVersions.AB_200, PackageVersions.AC_100, PackageVersions.BA_100]
            },
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [PackageVersions.AC_100]},
            Packages.AC: {PackageVersions.AC_100: [PackageVersions.BB_100, PackageVersions.BB_200]},
            Packages.BA: {PackageVersions.BA_100: [PackageVersions.BB_100, PackageVersions.BB_200]},
            Packages.BB: {
                PackageVersions.BB_100: [PackageVersions.BC_100, PackageVersions.BC_200],
                PackageVersions.BB_200: [PackageVersions.BC_100, PackageVersions.BC_200],
            },
            Packages.BC: {PackageVersions.BC_100: [], PackageVersions.BC_200: []},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={
                Packages.AA: {PackageVersions.AA_200},
                Packages.AC: {PackageVersions.AC_100},
                Packages.AB: {PackageVersions.AB_200},
            },
        )
        resolver.run()
        result_graph = resolver.result_graph
        assert [
            " - a:a:2.0.0",
            "    | - a:b:2.0.0",
            "    | - a:c:1.0.0",
            "    | - b:a:1.0.0",
            "        | - b:b:2.0.0",
            " - a:b:2.0.0",
            "    | - a:c:1.0.0",
            " - a:c:1.0.0",
            "    | - b:b:2.0.0",
            "        | - b:c:2.0.0",
        ] == result_graph.run()

    def test_circular_dependency(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [PackageVersions.AB_100]},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_100]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map, dependencies={Packages.AA: {PackageVersions.AA_100}}
        )
        resolver.run()
        result_graph = resolver.result_graph
        assert [" - a:a:1.0.0", "    | - a:b:1.0.0", "        | - a:a:1.0.0"] == result_graph.run()
