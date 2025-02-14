#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import platform
from argparse import ArgumentParser

from pkg_resources import parse_requirements

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.satresolver.core import Resolver
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.generate_requirements_file import generate_requirements
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_graph import PythonGraph

_logger = logging.getLogger(__name__)


class ResolverCLI(ToolchainBinary):
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--input-requirements", required=True, help="Path to requirements.txt")
        parser.add_argument("--output-path", required=True, help="Path to write output to.")
        parser.add_argument("--depgraph-url", required=True, help="URL to load leveldb depgraph from.")
        parser.add_argument("--requires-python", required=True, help="Version of python to resolve for. eg: 3.6")
        parser.add_argument("--abi", action="append", help="Any abi specifiers you support, eg: abi3")
        parser.add_argument(
            "--platform",
            help="Platform you want to resolve for. eg: macosx_10_14_x86_64. Defaults to current platform.",
        )

    def run(self) -> int:
        args = self.cmdline_args
        selected_platform = args.platform or platform.platform().replace("-", "_").replace(".", "_")
        with open(args.input_requirements) as f:
            lines = f.readlines()
        # parse_requirements handles empty or commented lines and will also throw errors on unparsable requirements.
        requirements = parse_requirements(lines)
        dependencies = [str(req) for req in requirements]
        graph = PythonGraph(
            Depgraph.from_url(args.depgraph_url),
            valid_abis=set(args.abi),
            requires_python=args.requires_python,
            platform=selected_platform,
        )
        config = PythonConfig.for_dependencies(dependencies=dependencies, graph=graph)
        resolver = Resolver(config)
        resolver.run()
        result = generate_requirements(resolver.result())
        with open(args.output_path, "w") as f:
            f.write(result)
        _logger.info(resolver.get_result())
        return 0


if __name__ == "__main__":
    ResolverCLI.start()
