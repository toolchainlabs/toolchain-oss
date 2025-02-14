# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.config import Config
from toolchain.satresolver.core import Resolver
from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.resolve_graph_to_json import (
    get_allowed_versions,
    get_depth_by_package,
    resolve_graph_to_json,
    resolve_result_to_json,
)
from toolchain.satresolver.test_helpers.core_test_data import Packages, PackageVersions

DEPENDENCIES = {Packages.AA: {PackageVersions.AA_300, PackageVersions.AA_400}}
TRANSITIVE_DEPENDENCY_MAP = {
    Packages.AA: {
        PackageVersions.AA_100: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
        ],
        PackageVersions.AA_200: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
        ],
        PackageVersions.AA_300: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        ],
        PackageVersions.AA_400: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        ],
    },
    Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
    Packages.AC: {PackageVersions.AC_100: [], PackageVersions.AC_200: [], PackageVersions.AC_300: []},
}


def get_config():
    return Config(dependencies=DEPENDENCIES, graph=DictGraph(transitive_dependency_map=TRANSITIVE_DEPENDENCY_MAP))


class TestResolveGraphToJson:
    def test_get_allowed_versions(self):
        resolver = Resolver(get_config())
        resolver.run()
        # PackageVersions.AA_100 and PackageVersions.AA_200 do not satisfy some constraints and are disallowed.
        expected_result = {
            PackageVersions.AA_300,
            PackageVersions.AA_400,
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        }
        assert resolver.result() != []
        assert expected_result == get_allowed_versions(assignments=resolver._solution._assignments)

    def test_get_depth_by_package(self):
        resolver = Resolver(get_config())
        resolver.run()
        expected_max_depth = 2
        expected_result = {Packages.AA: 1, Packages.AB: 2, Packages.AC: 2}
        assert resolver.result() != []
        assert (expected_max_depth, expected_result) == get_depth_by_package(resolver)

    def test_resolve_graph_to_json(self):
        resolver = Resolver(get_config())
        resolver.run()
        assert resolver.result() != []
        root_node = {
            "id": "__ROOT__",
            "package_version": "__ROOT__",
            "package_name": "__ROOT__",
            "version": "",
            "y_scale": 0.0,
            "in_solution": True,
            "is_incompatible": False,
            "_index": 0,
        }
        node_1 = {
            "id": str(PackageVersions.AA_100),
            "package_version": str(PackageVersions.AA_100),
            "package_name": Packages.AA,
            "version": PackageVersions.AA_100.version,
            "y_scale": 0.5,
            "in_solution": False,
            "is_incompatible": True,
            "_index": 1,
        }
        result = resolve_graph_to_json(resolver)
        nodes = result["nodes"]
        assert root_node == nodes[0]
        assert node_1 == nodes[1]
        groups = result["groups"]
        expected_groups = [
            ["__ROOT__"],
            [
                str(PackageVersions.AA_100),
                str(PackageVersions.AA_200),
                str(PackageVersions.AA_300),
                str(PackageVersions.AA_400),
            ],
            [str(PackageVersions.AC_100), str(PackageVersions.AC_200), str(PackageVersions.AC_300)],
            [str(PackageVersions.AB_100), str(PackageVersions.AB_200), str(PackageVersions.AB_300)],
        ]
        assert expected_groups == groups
        edges = result["edges"]
        expected_edges = [
            {"source": "a:a:3.0.0", "target": "a:b:2.0.0"},
            {"source": "a:a:3.0.0", "target": "a:b:3.0.0"},
            {"source": "a:a:3.0.0", "target": "a:b:1.0.0"},
            {"source": "a:a:3.0.0", "target": "a:c:2.0.0"},
            {"source": "a:a:3.0.0", "target": "a:c:3.0.0"},
            {"source": "a:a:3.0.0", "target": "a:c:1.0.0"},
            {"source": "a:a:4.0.0", "target": "a:b:2.0.0"},
            {"source": "a:a:4.0.0", "target": "a:b:3.0.0"},
            {"source": "a:a:4.0.0", "target": "a:b:1.0.0"},
            {"source": "a:a:4.0.0", "target": "a:c:2.0.0"},
            {"source": "a:a:4.0.0", "target": "a:c:3.0.0"},
            {"source": "a:a:4.0.0", "target": "a:c:1.0.0"},
            {"source": "a:a:1.0.0", "target": "a:b:2.0.0"},
            {"source": "a:a:1.0.0", "target": "a:b:1.0.0"},
            {"source": "a:a:1.0.0", "target": "a:c:2.0.0"},
            {"source": "a:a:1.0.0", "target": "a:c:1.0.0"},
            {"source": "a:a:2.0.0", "target": "a:b:2.0.0"},
            {"source": "a:a:2.0.0", "target": "a:b:3.0.0"},
            {"source": "a:a:2.0.0", "target": "a:b:1.0.0"},
            {"source": "a:a:2.0.0", "target": "a:c:2.0.0"},
            {"source": "a:a:2.0.0", "target": "a:c:1.0.0"},
            {"source": "__ROOT__", "target": "a:a:3.0.0"},
            {"source": "__ROOT__", "target": "a:a:4.0.0"},
        ]
        assert len(expected_edges) == len(edges)

    def test_resolve_result_to_json(self):
        expected = {
            "releases": [
                {"project_name": "a:a", "version": "4.0.0"},
                {"project_name": "a:b", "version": "3.0.0"},
                {"project_name": "a:c", "version": "3.0.0"},
            ],
            "dependencies": [{"source": "a:a", "target": "a:b"}, {"source": "a:a", "target": "a:c"}],
        }
        resolver = Resolver(get_config())
        resolver.run()
        assert expected == resolve_result_to_json(resolver)
