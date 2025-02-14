#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/devops/toolchain-remote-exec-workers

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/values.yaml" \
  > dist/toolchain-remote-exec-workers.yaml

yq eval dist/toolchain-remote-exec-workers.yaml
./src/sh/kubernetes/eval_manifest.sh dist/toolchain-remote-exec-workers.yaml