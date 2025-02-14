#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export K8S_VERSION=1.25

./prod/helm/services/remoting/proxy-server/test.sh
./prod/helm/services/remoting/storage-server/test.sh
./prod/helm/services/remoting/buildbox/test.sh
