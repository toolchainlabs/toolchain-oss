#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# shellcheck disable=SC1091
source ../terraform_list.sh

function tf_projects {
  # In implicit dependency order.
  # shellcheck disable=SC2034
  local TF_PROJECTS=(
    "region"
    "s3"
    "vpc"
    "vpc-peering"
    "cognito"
    "bastion"
    "lambda"
    "opensearch"
    "vpn"
    "dbs"
    "kubernetes"
    "devbox"
    "cloudfront"
    "elasticache/redis"
    "waf"
    "efs"
    "sns"
    "ecr"
  )
  terraform_list "$@"
}

tf_projects "$@"
