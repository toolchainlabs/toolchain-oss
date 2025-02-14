#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/db/username.sh

# Ensure the user's dev namespace exists, and set it as the default.

if [ $# -ne 1 ]; then
  echo "Usage: $0 <cluster name>"
  exit 1
fi

cluster_name=$1

# Check that this isn't a prod cluster!
if [[ "${cluster_name}" =~ ^prod-.* ]]; then
  echo "Cannot create dev namespace on production cluster ${cluster_name}!"
  exit 1
fi

NAMESPACE=$(get_username)

./src/sh/kubernetes/create_namespace.sh "${NAMESPACE}"

kubectl config set-context "${cluster_name}" --namespace="${NAMESPACE}"
