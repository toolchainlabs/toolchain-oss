#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/util/logging.sh
source ./src/sh/util/docker.sh

debug "Building Redis CLI image at rev ${IMAGE_TAG} ..."

remote_tag="${PRIVATE_IMAGE_REGISTRY:-}tools/redis-cli:latest"
docker build --platform=linux/amd64 prod/docker/tools/redis-cli -t "${remote_tag}"

if [ -z "${NO_PUSH:-}" ]; then
  ecr_login_private

  debug "Pushing Devops CI image ..."
  docker push "${remote_tag}"

  info "Published new devops image to ${remote_tag}"
else
  info "Would have published new devops ci image to ${remote_tag}"
fi
