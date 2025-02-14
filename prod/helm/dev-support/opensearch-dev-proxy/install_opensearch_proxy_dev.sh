#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

source ./src/sh/db/username.sh
# Get the namespace that kubectl accesses by default, which is the one we'll install to.
NAMESPACE=$(kubectl config get-contexts "$(kubectl config current-context)" | awk 'NR > 1 {print $5}')
RELEASE="${NAMESPACE}-opensearch-dev-proxy"
helm upgrade --install "${RELEASE}" prod/helm/dev-support/opensearch-dev-proxy/ --kube-context=dev-e1-1 --namespace "${NAMESPACE}"
