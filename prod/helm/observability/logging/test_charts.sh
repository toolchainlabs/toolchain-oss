#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

CHART_DIR=prod/helm/observability/logging

helm dependency update "${CHART_DIR}"

helm template  "${CHART_DIR}" \
     --kube-version "${K8S_VERSION}" --debug \
     --values  "${CHART_DIR}/fake_values_dev.yaml" > dist/logging-manifests-dev.yaml

helm template  "${CHART_DIR}" \
     --kube-version "${K8S_VERSION}" --debug \
     --values  "${CHART_DIR}/fake_values_prod.yaml" > dist/logging-manifests-prod.yaml

./src/sh/kubernetes/eval_manifest.sh dist/logging-manifests-dev.yaml
./src/sh/kubernetes/eval_manifest.sh dist/logging-manifests-prod.yaml