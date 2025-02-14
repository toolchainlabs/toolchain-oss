#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/payments/api/payments-api
cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm dependency update "${CHART_DIR}"

helm template \
  "${CHART_DIR}" \
 --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/payments-api-dev.yaml

yq eval dist/payments-api-dev.yaml

./src/sh/kubernetes/eval_manifest.sh dist/payments-api-dev.yaml