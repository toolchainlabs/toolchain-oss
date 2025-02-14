# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path

from toolchain.satresolver.core import Resolver
from toolchain.satresolver.pypi.generate_requirements_file import generate_requirements
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_graph import PythonGraph
from toolchain.satresolver.test_helpers.pypi_test_data import Distributions
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph


def test_generate_requirements(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_200_whl_33,
        Distributions.bbb_100_whl_27,
        Distributions.bbb_100_whl_33,
    )
    graph = PythonGraph(depgraph, requires_python="2.7.6", platform="any")
    config = PythonConfig.for_dependencies(dependencies=["bbb==1.0.0"], graph=graph)
    resolver = Resolver(config)
    resolver.run()
    aaa_sha256 = "d0c06aec68f4fb780212b0eaf74325bee64bf64add491bb2c8dd578d1677b9bf"
    bbb_sha256 = "dba712ebb770623ca9d78efe273b0598355e60bd34a9858ea31ab4ed962989b0"
    expected_result = f"aaa==1.0.0 --hash=sha256:{aaa_sha256}\nbbb==1.0.0 --hash=sha256:{bbb_sha256}"
    assert expected_result == generate_requirements(resolver.result())
