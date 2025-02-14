#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

kubectl apply \
  --context="remoting-prod-e1-1" \
  -f prod/kubernetes/configs/remoting-prod-e1-1/auth/aws_users_config_map.yaml
