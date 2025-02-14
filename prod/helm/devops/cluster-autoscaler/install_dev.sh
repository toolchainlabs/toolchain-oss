#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
CHART_DIR=prod/helm/devops/cluster-autoscaler
helm dependency update "${CHART_DIR}"

helm upgrade --install cluster-autoscaler "${CHART_DIR}" --namespace=kube-system --kube-context=dev-e1-1 --values="${CHART_DIR}/values-dev.yaml" 
