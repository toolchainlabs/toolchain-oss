#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/services/webhooks/webhooks

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm dependency update "${CHART_DIR}"

helm template \
  "${CHART_DIR}" \
 --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_dev.yaml" \
  > dist/webhooks-dev.yaml

yq eval dist/webhooks-dev.yaml

helm template \
  "${CHART_DIR}" \
 --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values_prod.yaml" \
  > dist/webhooks-prod.yaml

yq eval dist/webhooks-prod.yaml

./src/sh/kubernetes/eval_manifest.sh dist/webhooks-prod.yaml
./src/sh/kubernetes/eval_manifest.sh dist/webhooks-dev.yaml