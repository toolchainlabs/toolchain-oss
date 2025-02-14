#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/dev-support/dev-prometheus

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/
helm dependency update "${CHART_DIR}"
helm template "${CHART_DIR}" \
    --kube-version "${K8S_VERSION}" --debug \
    --values="${CHART_DIR}/values.yaml" > dist/dev-prometheus.yaml

yq eval dist/dev-prometheus.yaml

# `apiVersion: apiregistration.k8s.io/v1beta1 kind: APIService` is not avaibale in the upsream schema repos. so we ignore it for now.
./src/sh/kubernetes/eval_manifest.sh -skip APIService dist/dev-prometheus.yaml