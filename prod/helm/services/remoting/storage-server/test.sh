#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/remoting/storage-server

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/remoting-storage-server-dev.yaml

yq eval dist/remoting-storage-server-dev.yaml

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --api-versions monitoring.coreos.com/v1 \
  --values="${CHART_DIR}/test_values_prod.yaml" \
  > dist/remoting-storage-server-prod.yaml

yq eval dist/remoting-storage-server-prod.yaml

./src/sh/kubernetes/eval_manifest.sh dist/remoting-storage-server-prod.yaml
./src/sh/kubernetes/eval_manifest.sh dist/remoting-storage-server-dev.yaml