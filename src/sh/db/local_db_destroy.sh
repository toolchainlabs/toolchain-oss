#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Destroys dev database on the local machine.

# Notes:
# - This script deletes all data associated with the database!
# - This script is idempotent and can safely be run multiple times, e.g., to create new logical databases.

source ./src/sh/db/db_names.sh
source ./src/sh/db/local_db_common.sh

if [ -d "${DATADIR}" ]; then
  pg_ctl stop -D "${DATADIR}" || true
  rm -rf "${DATADIR}"
  echo "Deleted ${DATADIR}"
else
  echo "No database at ${DATADIR}"
fi

function delete_secret() {
  secret_name="${INSTANCE_NAME}-${1}-creds"
  rm -f "$HOME/.toolchain_secrets_dev/${secret_name}"
  echo "Deleted secret ${secret_name}"
}

function delete_secret_simple() {
  secret_name="${INSTANCE_NAME}-${1}-simple-creds"
  rm -f "$HOME/.toolchain_secrets_dev/${secret_name}"
  echo "Deleted secret ${secret_name}"
}

delete_secret master

for db_name in ${DB_NAMES}; do
  delete_secret "${db_name}"
done

for db_name in ${SIMPLE_DB_NAMES}; do
  delete_secret_simple "${db_name}"
done
