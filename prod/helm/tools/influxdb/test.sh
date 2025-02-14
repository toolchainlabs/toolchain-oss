#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/tools/influxdb

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/
helm dependency update "${CHART_DIR}"

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/fake_values.yaml" \
  > dist/influxdb_manifests.yaml

yq eval dist/influxdb_manifests.yaml
./src/sh/kubernetes/eval_manifest.sh dist/influxdb_manifests.yaml