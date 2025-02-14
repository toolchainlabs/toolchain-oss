#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Sets up a dev database on the local machine.

# Notes:
# - This script is idempotent and can safely be run multiple times, e.g., to create new logical databases,
#   or rerun the local db after restarting the machine or killing the process.

source ./src/sh/db/db_names.sh
source ./src/sh/db/local_db_common.sh
source ./src/sh/db/check_django.sh

cmd=$(
  cat << EOF
pants run src/python/toolchain/util/db:launch_db_on_local_machine --   \
  --instance-name "${INSTANCE_NAME}" \
  --location "${DATADIR}"
EOF
)

for db_name in ${DB_NAMES}; do
  cmd+=" --db ${db_name}"
done

for db_name in ${SIMPLE_DB_NAMES}; do
  cmd+=" --simple-db ${db_name}"
done

eval "${cmd}"

./src/sh/db/migrate.sh
if [ "${1:-}" != "--no-bootstrap" ]; then
  ./src/sh/db/bootstrap_dev_db.sh
else
  echo "Skip DB bootstrap"
fi
