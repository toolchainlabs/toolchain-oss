#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./pants run src/python/toolchain/prod/installs/build_install_remote_cache_reporter.py -- --prod "$@"