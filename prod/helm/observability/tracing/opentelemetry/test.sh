#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/observability/tracing/opentelemetry

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --api-versions monitoring.coreos.com/v1 \
  --values="${CHART_DIR}/test_values.yaml" \
  > dist/opentelemetry_manifests_prod.yaml


helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values.yaml" \
  > dist/opentelemetry_manifests_dev.yaml


yq eval dist/opentelemetry_manifests_prod.yaml
yq eval dist/opentelemetry_manifests_dev.yaml
./src/sh/kubernetes/eval_manifest.sh  dist/opentelemetry_manifests_prod.yaml
./src/sh/kubernetes/eval_manifest.sh  dist/opentelemetry_manifests_dev.yaml
