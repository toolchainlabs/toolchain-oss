#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export K8S_VERSION=1.25

./prod/helm/observability/monitoring/test_charts.sh
./prod/helm/observability/logging/test_charts.sh
./prod/helm/observability/tracing/opentelemetry/test.sh
