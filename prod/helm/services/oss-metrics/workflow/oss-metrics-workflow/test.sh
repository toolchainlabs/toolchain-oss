#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/oss-metrics/workflow/oss-metrics-workflow

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm dependency update "${CHART_DIR}"

helm template \
  "${CHART_DIR}" \
 --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/oss-metrics-workflow-dev.yaml

yq eval dist/oss-metrics-workflow-dev.yaml
./src/sh/kubernetes/eval_manifest.sh dist/oss-metrics-workflow-dev.yaml