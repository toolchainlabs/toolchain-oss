#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A script to build and install a chart directly from its loose sources, for dev purposes.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./pants package src/python/toolchain/prod/installs/build_install_services_dev.py
./dist/src.python.toolchain.prod.installs/build_install_services_dev.pex "$@"