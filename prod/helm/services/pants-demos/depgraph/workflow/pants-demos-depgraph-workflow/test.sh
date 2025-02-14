#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/pants-demos/depgraph/workflow/pants-demos-depgraph-workflow

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm dependency update "${CHART_DIR}"

helm template \
  "${CHART_DIR}" \
 --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/pants-demos-depgraph-workflow-dev.yaml

yq eval dist/pants-demos-depgraph-workflow-dev.yaml
./src/sh/kubernetes/eval_manifest.sh dist/pants-demos-depgraph-workflow-dev.yaml