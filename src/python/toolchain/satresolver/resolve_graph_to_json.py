# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import itertools

from toolchain.satresolver.core import Resolver
from toolchain.satresolver.package import ROOT
from toolchain.satresolver.partial_solution import PartialSolution
from toolchain.satresolver.term import RootConstraint


def get_allowed_versions(assignments):
    """Generate the set of possible package_versions.

    Excludes assignments made as decisions between possible versions as opposed to derived from constraints.
    """
    partial_solution = PartialSolution()
    for assignment in assignments:
        if not assignment.is_decision:
            partial_solution._register(assignment)
    allowed_versions = set()
    for term in partial_solution._terms.values():
        allowed_versions.update(term.allowed_versions)
    return allowed_versions


def get_depth_by_package(resolver):
    """Returns a map from each package to the shallowest depth at which it is found in the transitive dependency
    tree."""
    res_graph = resolver.result_graph
    res_graph.run()
    max_depth = max(res_graph.depth.values())
    return max_depth, {package_version.subject: depth for package_version, depth in res_graph.depth.items()}


def resolve_graph_to_json(resolver):
    """Turns resolve data into json serializable node and edge structures the d3 graph can use."""
    allowed_versions = get_allowed_versions(resolver._solution._assignments)

    def is_incompatible(package_version):
        return package_version not in allowed_versions and package_version != ROOT

    dependency_map = resolver._config._graph._dependency_map
    package_versions = dependency_map.keys()
    max_depth, depth_by_package = get_depth_by_package(resolver)
    sorted_packages = sorted(package_versions)
    package_version_to_index = {package_version: index for index, package_version in enumerate(sorted_packages)}

    def nodes_iter():
        """One node per package_version in the transitive dependency graph."""
        for package_version in package_versions:
            # TODO: This code shouldn't know about anything python-specific.
            if package_version.subject != "PythonInterpreter":
                yield {
                    "id": str(package_version),
                    "package_version": str(package_version),
                    "package_name": package_version.subject,
                    "version": package_version.version,
                    "y_scale": depth_by_package.get(package_version.subject, 0) / max_depth,
                    "in_solution": package_version in resolver.result() or package_version == ROOT,
                    "is_incompatible": is_incompatible(package_version),
                    "_index": package_version_to_index[package_version],
                }

    def edges_iter():
        for package_version in package_versions:
            dependencies = itertools.chain.from_iterable(dependency_map[package_version].values())
            for dep in dependencies:
                yield {
                    "source": "__ROOT__" if package_version == RootConstraint else str(package_version),
                    "target": str(dep),
                }

    def groups_iter():
        """Groups are used to collect versions of the same package together in the graph."""
        for subject, version_set in resolver._config._graph._packages.items():
            if subject != "PythonInterpreter" and version_set:
                yield sorted(str(package_version) for package_version in version_set)

    return {
        "nodes": sorted(nodes_iter(), key=lambda node: node["_index"]),
        "edges": list(edges_iter()),
        "groups": [["__ROOT__"]] + [group for group in groups_iter() if group],
    }


def resolve_result_to_json(resolver: Resolver) -> dict:
    """Returns the result of a resolve as a json-serializable dict."""
    releases = []
    for item in sorted(resolver.result()):
        releases.append({"project_name": item.package_name, "version": item.version})
        sha256 = getattr(item, "sha256", None)
        if sha256:
            releases[-1]["sha256"] = sha256.hex()
    return {
        "releases": releases,
        "dependencies": [
            {"source": src, "target": tgt} for src, tgt in sorted(resolver.get_dependency_edges_for_result())
        ],
    }
