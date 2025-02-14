#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export K8S_VERSION=1.25

./prod/helm/aws/aws-alb-ingress-controller/test_chart.sh
./prod/helm/aws/external-dns/test_chart.sh
./prod/helm/aws/aws-efs-csi-driver/test_chart.sh
