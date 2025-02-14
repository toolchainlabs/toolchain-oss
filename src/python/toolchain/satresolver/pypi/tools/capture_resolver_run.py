# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from typing import cast

from django.conf import settings

from toolchain.base.fileutil import write_file
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.lang.python.distributions.distribution_key import canonical_project_name
from toolchain.satresolver.core import Resolver
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution
from toolchain.satresolver.pypi.python_graph import PythonGraph, get_abi_for_python_version


def _flatten_dependency_map(data) -> Iterator[PythonPackageDistribution]:
    for key, value in data.items():
        if isinstance(key, PythonPackageDistribution):
            yield key
        if isinstance(value, PythonPackageDistribution):
            yield value
        elif isinstance(value, frozenset):
            yield from value
        elif isinstance(value, dict):
            yield from _flatten_dependency_map(value)
        else:
            raise ToolchainAssertion(f"Unknown value type: {type(value)}")


def _dist_to_dict(dist: PythonPackageDistribution) -> dict:
    return {
        "key": asdict(dist.key),
        "value": {"sha256": base64.b64encode(dist.sha256).decode(), "requires": list(dist.value.requires)},
    }


def capture_resolver_run(
    requirements_file: str,
    output_fixture: str,
    python: str = "3.6",
    platform="macosx_10_15_x86_64",
    abis: Iterable[str] | None = None,
) -> None:
    with open(requirements_file) as fl:
        requirements = [canonical_project_name(req) for req in fl.readlines()]
    valid_abis = list(abis or get_abi_for_python_version(python))
    with settings.DEPGRAPH.get() as depgraph:
        graph = PythonGraph(depgraph, requires_python=python, valid_abis=set(valid_abis), platform=platform)
        config = PythonConfig.for_requirements(
            requirements=PythonGraph.parse_requirements(requirements), graph=graph, override_reqs=True
        )
        resolver = Resolver(config)
        result = cast(list[PythonPackageDistribution], resolver.run())
    fixture = {
        "parameters": {"python": python, "abis": valid_abis, "platform": platform, "requirements": requirements},
        "depgraph": [_dist_to_dict(dist) for dist in _flatten_dependency_map(graph._dependency_map)],
        "results": [_dist_to_dict(dist) for dist in result],
    }
    write_file(output_fixture, json.dumps(fixture, indent=4))
