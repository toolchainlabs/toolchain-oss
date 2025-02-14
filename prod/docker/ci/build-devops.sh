#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# a script to build and push the image we run CI-devops job in.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/util/logging.sh
source ./src/sh/util/docker.sh

debug "Building Devops CI image at rev ${IMAGE_TAG} ..."

remote_tag="${PRIVATE_IMAGE_REGISTRY:-}ci-devops:${IMAGE_TAG:-dev}"
docker build --platform=linux/amd64 --file=prod/docker/ci/Dockerfile.devops prod/docker/ci -t "${remote_tag}"

if [ -z "${NO_PUSH:-}" ]; then
  ecr_login_private

  debug "Pushing Devops CI image ..."
  docker push "${remote_tag}"

  info "Published new devops image to ${remote_tag}"
else
  info "Would have published new devops ci image to ${remote_tag}"
fi
