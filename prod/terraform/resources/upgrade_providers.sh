#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

./terraform_all.sh init -upgrade
./terraform_all.sh providers lock
./terraform_all.sh providers lock -platform=darwin_amd64 -platform=darwin_arm64 -platform=linux_amd64
