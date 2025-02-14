#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/devops/aws-cost-reporter

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/

helm template \
  "${CHART_DIR}" \
  --kube-version "${K8S_VERSION}" --debug \
  --values="${CHART_DIR}/test_values.yaml" \
  > dist/devops-aws-cost-reporter.yaml

yq eval dist/devops-aws-cost-reporter.yaml

./src/sh/kubernetes/eval_manifest.sh dist/devops-aws-cost-reporter.yaml