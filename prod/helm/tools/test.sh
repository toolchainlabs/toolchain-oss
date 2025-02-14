#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export K8S_VERSION=1.25

./prod/helm/tools/influxdb/test.sh
# Disabled tools we don't currenly use/deploy
# ./prod/helm/tools/cert-manager/test.sh
# ./prod/helm/tools/posthog/test.sh
