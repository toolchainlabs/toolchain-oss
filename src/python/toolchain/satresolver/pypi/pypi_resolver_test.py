# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
from collections.abc import Iterator
from pathlib import Path

import pytest

from toolchain.lang.python.distributions.distribution_key import DistributionKey
from toolchain.satresolver.cause import ConflictCause, NoVersionsCause
from toolchain.satresolver.core import ResolutionError, Resolver
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution, ResolutionData
from toolchain.satresolver.pypi.python_graph import PythonGraph
from toolchain.satresolver.term import VersionConstraint
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph_for_dists, load_fixture


def load_dists(dists_json) -> Iterator[PythonPackageDistribution]:
    for dist in dists_json:
        key = DistributionKey(**dist["key"])
        sha256 = base64.b64decode(dist["value"]["sha256"])
        requires = tuple(dist["value"]["requires"])
        yield PythonPackageDistribution.create(key=key, value=ResolutionData(sha256=sha256, requires=requires))


def get_test_resolver(depgraph: Depgraph, fixture: dict) -> Resolver:
    params = fixture["parameters"]
    requirements = PythonGraph.parse_requirements(params["requirements"])
    graph = PythonGraph(
        depgraph, requires_python=params["python"], valid_abis=set(params["abis"]), platform=params["platform"]
    )
    config = PythonConfig.for_requirements(requirements=requirements, graph=graph, override_reqs=True)
    return Resolver(config)


@pytest.mark.parametrize("fixture_name", ["resolver_1", "resolver_2", "resolver_3", "duplicate_reqs", "resolver_4"])
def test_resolver(tmp_path: Path, fixture_name: str) -> None:
    fixture = load_fixture(fixture_name)
    depgraph = create_fake_depgraph_for_dists(tmp_path, load_dists(fixture["depgraph"]))
    resolver = get_test_resolver(depgraph, fixture)
    expected_results = list(load_dists(fixture["results"]))
    result = resolver.run()
    assert result == expected_results


def test_missing_dependency(tmp_path: Path) -> None:
    """In this test we manipulate the depgraph data and dropping 'setuptools' from it With the parameters we run the
    resolver in this test, gunicorn, which is the only requirement we are trying to resolve for, effectively depends
    only on setuptools, so by removing setuptools, we test that the resolver fails if there is a dependency on a non-
    existent package."""

    fixture = load_fixture("resolver_1")
    dists_iter = (dist for dist in load_dists(fixture["depgraph"]) if dist.package_name != "setuptools")
    depgraph = create_fake_depgraph_for_dists(tmp_path, dists_iter)
    resolver = get_test_resolver(depgraph, fixture)
    with pytest.raises(ResolutionError, match="Could not resolve conflict for Incompatibility") as error_info:
        resolver.run()
    cause = error_info.value._failure.cause
    assert isinstance(cause, ConflictCause)
    assert isinstance(cause.conflict.cause, NoVersionsCause)
    assert len(cause.conflict.terms) == 1
    first_term = cause.conflict.terms[0]
    assert isinstance(first_term, VersionConstraint)
    assert first_term.package_name == "gunicorn"
