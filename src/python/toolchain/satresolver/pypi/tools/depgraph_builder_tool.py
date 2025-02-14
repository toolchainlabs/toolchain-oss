#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.pypi.depgraph_builder import DepgraphBuilder
from toolchain.util.leveldb.builder_binary import BuilderBinary


class DepgraphBuilderBinary(BuilderBinary):
    BuilderClass = DepgraphBuilder


if __name__ == "__main__":
    DepgraphBuilderBinary.start()
