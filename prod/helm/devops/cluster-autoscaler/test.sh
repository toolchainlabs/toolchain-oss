#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/devops/cluster-autoscaler

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm dependency update "${CHART_DIR}"

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/values-dev.yaml" \
  > dist/devops-cluster-autoscaler.yaml

yq eval dist/devops-cluster-autoscaler.yaml
./src/sh/kubernetes/eval_manifest.sh dist/devops-cluster-autoscaler.yaml