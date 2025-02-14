#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

CHART_DIR=prod/helm/devops/kubernetes-dashboard

helm dependency update "${CHART_DIR}"

helm upgrade --install kubernetes-dashboard "${CHART_DIR}" \
     --namespace=kubernetes-dashboard --kube-context=remoting-prod-e1-1 \
     --values "${CHART_DIR}/values.yaml" \
     --set kubernetes-dashboard.serviceMonitor.enabled=true
