#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/remoting/buildbox

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --api-versions monitoring.coreos.com/v1 \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/buildbox-manifests-dev.yaml

yq eval dist/buildbox-manifests-dev.yaml
 