#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Stops the dev database on the local machine.

source ./src/sh/db/local_db_common.sh

pg_ctl stop -D "${DATADIR}"
