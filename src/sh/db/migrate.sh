#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Runs the initial migrations to populate dev dbs.

# In the presence of multiple databases, Django is finicky about running migrations in a specific order.
# This script does the right thing, so you don't need to think about it.
#
# Notes:
#
# - If you create new migrations for any database, re-run this script to apply them.
# - This script is idempotent and can safely be run multiple times.
# - Running w/ collect static mode to prevent toolshed from trying to load secrets that are not needed in order to run migrations.

TOOLCHAIN_ENV=toolchain_dev DEV_ONLY_CONFIGURE_DBS=true pants run src/python/toolchain/service/toolshed:toolshed-manage -- migrate_all
