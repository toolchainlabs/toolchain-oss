#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# A script to set up a dev database on Kubernetes.

# Notes:
# - This script assumes that the user's kubectl points to the appropriate cluster.
# - This script is idempotent and can safely be run multiple times, e.g., to create new logical databases.

source ./src/sh/db/db_names.sh
source ./src/sh/db/dev_db_common.sh

STORAGE_GB="${3-1}"

echo "Creating dev database '${RELEASE_NAME}' in namespace '${NAMESPACE}' storage ${STORAGE_GB}GB"

source ./src/sh/db/check_django.sh

./src/sh/kubernetes/create_namespace.sh "${NAMESPACE}"

cmd=$(
  cat << EOF
./src/python/toolchain/util/db/launch_db_on_kubernetes.py \
  --namespace ${NAMESPACE} \
  --release-name ${RELEASE_NAME} \
  --storage-gb ${STORAGE_GB}
EOF
)

for db_name in ${DB_NAMES}; do
  cmd+=" --db ${db_name}"
done

for db_name in ${SIMPLE_DB_NAMES}; do
  cmd+=" --simple-db ${db_name}"
done

eval "${cmd}"

USE_REMOTE_DEV_DBS=1 DEV_NAMESPACE_OVERRIDE="${NAMESPACE}" ./src/sh/db/migrate.sh
USE_REMOTE_DEV_DBS=1 DEV_NAMESPACE_OVERRIDE="${NAMESPACE}" ./src/sh/db/bootstrap_dev_db.sh
