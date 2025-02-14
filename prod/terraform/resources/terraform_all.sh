#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

. ./terraform_list.sh

function tf_projects {
  # In implicit dependency order.
  local TF_PROJECTS=(
    "global"
    "global/pagerduty/services"
    "global/statuscake"
    "global/route53"
    "global/ses_email"
    "global/iam"
    "us-east-1"
  )
  terraform_list "$@"
}

tf_projects "$@"
