#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

CHART_DIR=prod/helm/dev-support/dev-prometheus

helm dependency update "${CHART_DIR}"
helm upgrade --install dev-prometheus "${CHART_DIR}" \
        --namespace monitoring --kube-context=dev-e1-1 \
        --values="${CHART_DIR}/values.yaml"
