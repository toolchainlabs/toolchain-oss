#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Set up the local kubectl to point to the specified Kubernetes cluster.
# Assumes that the awscli is installed, and that the default local AWS user
# has permissions to access that cluster.

keep_current_context=false
if [ "$1" = "--keep-current" ]; then
  keep_current_context=true
  shift
fi

if [ $# -ne 1 ]; then
  echo "Usage: kubectl_setup.sh [--keep-current] <cluster name>"
  echo "  --keep-current   Do not change kubectl's current context."
  exit 1
fi

cluster_name="$1"

if $keep_current_context ; then
  current_context="$(kubectl config current-context)"
fi

aws eks update-kubeconfig --name "${cluster_name}" --alias "${cluster_name}"

if $keep_current_context ; then
  kubectl config use-context "${current_context}"
fi
