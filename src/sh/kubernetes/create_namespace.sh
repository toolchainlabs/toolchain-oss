#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Create a Kubernetes namespace on the cluster currently pointed to by kubectl.
# Idempotent: Re-creating an existing namespace is a no-op.

if [ $# -lt 1 ]; then
  echo "Usage: $0 <namespace>"
  exit 1
fi

NAMESPACE=$1

echo "Creating namespace ${NAMESPACE}"

# ns_type is used in ClusterAPI.list_namespaces.

cat << EOF | kubectl apply --context=dev-e1-1 -f -
kind: Namespace
apiVersion: v1
metadata:
  name: ${NAMESPACE}
  labels:
    ns_type: engineer
    name: ${NAMESPACE}
EOF
