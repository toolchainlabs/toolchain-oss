# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path

from toolchain.satresolver.core import Resolver
from toolchain.satresolver.package import ROOT
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_graph import PythonGraph
from toolchain.satresolver.test_helpers.pypi_test_data import AAA, BBB, CCC, Distributions
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph


def test_resolve_with_platform_constraint(tmp_path: Path) -> None:
    expected_result = [Distributions.aaa_100_whl_27_win, Distributions.bbb_100_whl_27]
    depgraph = create_fake_depgraph(
        tmp_path, Distributions.aaa_100_whl_27_osx, Distributions.aaa_100_whl_27_win, Distributions.bbb_100_whl_27
    )
    graph = PythonGraph(depgraph, requires_python="2.7.6", platform="win_amd64")
    config = PythonConfig.for_dependencies(dependencies=[BBB], graph=graph)
    resolver = Resolver(config)
    resolver.run()
    assert expected_result == resolver.result()


def test_format_overrides(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_200_whl_33,
        Distributions.aaa_100_whl_27_win,
        Distributions.aaa_100_whl_27_osx,
    )
    graph = PythonGraph(depgraph, valid_abis={"none", ""}, requires_python="3.3", platform="any")
    config = PythonConfig.for_dependencies(dependencies=[], overrides=["AAA==1.0"], graph=graph)
    expected_overrides = {AAA: {Distributions.aaa_100_whl_33}}
    assert config.overrides == expected_overrides


def test_resolve_with_override(tmp_path: Path) -> None:
    expected_result = [Distributions.aaa_200_whl_33, Distributions.ccc_100_whl_33]
    depgraph = create_fake_depgraph(
        tmp_path, Distributions.aaa_100_whl_33, Distributions.aaa_200_whl_33, Distributions.ccc_100_whl_33
    )
    graph = PythonGraph(depgraph, requires_python="3.3", platform="win_amd64")
    config = PythonConfig.for_dependencies(dependencies=[CCC], overrides=["AAA==2.0"], graph=graph)
    resolver = Resolver(config)
    resolver.run()
    assert expected_result == resolver.result()


def test_incompatibilities_for(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(tmp_path)
    config = PythonConfig.for_dependencies(
        dependencies=[], graph=PythonGraph(depgraph, requires_python="2.7.6", platform="any")
    )
    assert not list(config.incompatibilities_for(ROOT))


def test_incompatibilities_for_package(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(tmp_path)
    config = PythonConfig.for_dependencies(
        dependencies=[], graph=PythonGraph(depgraph, requires_python="2.7.6", platform="any")
    )
    assert config.incompatibilities_for_package("python") is None
