#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./pants run src/python/toolchain/prod/installs/install_influxdb.py -- --orgs buildsense "$@"