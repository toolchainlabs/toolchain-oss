#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/remoting/execution-server

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/remoting-execution-server-dev.yaml

yq eval dist/remoting-execution-server-dev.yaml

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --api-versions monitoring.coreos.com/v1 \
  --values="${CHART_DIR}/test_values_prod.yaml" \
  > dist/remoting-execution-server-prod.yaml

yq eval dist/remoting-execution-server-prod.yaml
./src/sh/kubernetes/eval_manifest.sh dist/remoting-execution-server-prod.yaml
./src/sh/kubernetes/eval_manifest.sh dist/remoting-execution-server-dev.yaml