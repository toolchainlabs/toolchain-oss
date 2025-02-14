# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.util.leveldb.builder import Builder

logger = logging.getLogger(__name__)


class BuilderBinary(ToolchainBinary):
    """Utility binary to build a leveldb table from some input data."""

    BuilderClass: type[Builder]  # Subclasses must set.

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--input-url", required=True, action="append", help="The URL of a file or dir containing input data."
        )
        parser.add_argument(
            "--output-dir-url", required=True, help="The URL of the dir to which to write the output data."
        )
        parser.add_argument(
            "--existing-leveldb-dir-url", help="If a leveldb database exists at this location, use its data as a base."
        )
        parser.add_argument(
            "--write-batch-size", type=int, default=100000, help="How many items to batch before writing."
        )

    def __init__(self, cmdline_args: Namespace) -> None:
        super().__init__(cmdline_args)
        self._builder = self.BuilderClass(
            cmdline_args.input_url,
            cmdline_args.output_dir_url,
            cmdline_args.existing_leveldb_dir_url,
            cmdline_args.write_batch_size,
        )

    def run(self) -> int:
        self._builder.run()
        return 0
