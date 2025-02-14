#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./pants run src/python/toolchain/prod/installs/install_opentelemetry.py -- --cluster=dev-e1-1
