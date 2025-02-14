#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A script to install/upgrade the monitoring helm chart on the production cluster.
# USE WITH CAUTION - THIS AFFECTS PRODUCTION!

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./pants run src/python/toolchain/prod/installs:install_monitoring_prod -- --cluster=prod-e1-1 "$@"
