#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Runs a Django command to bootstrap dev db, create a Customer, Repo and an admin toolchain user
# Since we use github login, the user will be prompted both github username (handle) and toolchain email alias

pants run src/python/toolchain/service/users/ui:users-ui-manage -- bootstrap
