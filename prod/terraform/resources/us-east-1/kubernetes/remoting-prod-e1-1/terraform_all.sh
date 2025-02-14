#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# shellcheck disable=SC1091
source ../../../terraform_list.sh

function tf_projects {
  # In implicit dependency order.
  # shellcheck disable=SC2034
  local TF_PROJECTS=(
    "control_plane"
    "nodes"
    "service_role_policies"
  )
  terraform_list "$@"
}

tf_projects "$@"
