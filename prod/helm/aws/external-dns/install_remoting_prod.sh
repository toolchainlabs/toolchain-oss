#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A script to install/upgrade the external-dns chart on the remoting prod cluster
# USE WITH CAUTION - THIS AFFECTS PRODUCTION!

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./src/python/toolchain/prod/installs/install_external_dns_prod.py --cluster=remoting-prod-e1-1 "$@"
