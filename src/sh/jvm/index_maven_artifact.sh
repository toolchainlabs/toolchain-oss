#!/usr/bin/env bash
# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -e

# Convenience wrapper for running the source indexer on a maven artifact.
./pants run src/python/toolchain/crawler:source_indexer -- "$@"
