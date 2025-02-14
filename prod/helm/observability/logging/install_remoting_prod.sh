#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A script to install/upgrade the logging helm chart on the production cluster.
# USE WITH CAUTION - THIS AFFECTS PRODUCTION!

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./src/python/toolchain/prod/installs/install_logging_prod.py --cluster=remoting-prod-e1-1  "$@"
