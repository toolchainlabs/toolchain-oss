#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
CHART_DIR=prod/helm/devops/toolchain-remote-exec-workers
helm upgrade --install toolchain-remote-exec-workers "${CHART_DIR}" --namespace=remote-exec --kube-context=dev-e1-1
