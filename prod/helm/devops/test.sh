#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export K8S_VERSION=1.25

./prod/helm/devops/cluster-autoscaler/test.sh
./prod/helm/devops/aws-cost-reporter/test.sh
./prod/helm/devops/db-creds-rotator/test.sh
./prod/helm/devops/iam-keys-watcher/test.sh
./prod/helm/devops/kubernetes-dashboard/test.sh
./prod/helm/devops/remote-cache-usage-reporter/test.sh
./prod/helm/devops/toolchain-remote-exec-workers/test.sh

