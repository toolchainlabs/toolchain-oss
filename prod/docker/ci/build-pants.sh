#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# a script to build and push the image we run CI jobs in.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/util/logging.sh
source ./src/sh/util/docker.sh

debug "Building Pants CI image at rev ${IMAGE_TAG} ..."

remote_tag="${PRIVATE_IMAGE_REGISTRY:-}ci:${IMAGE_TAG:-dev}"
docker build --platform=linux/amd64 --file=prod/docker/ci/Dockerfile.pants prod/docker/ci -t "${remote_tag}"

if [ -z "${NO_PUSH:-}" ]; then
  ecr_login_private

  debug "Pushing Pants CI image ..."
  docker push "${remote_tag}"

  info "Published new Pants image to ${remote_tag}"
else
  info "Would have published new Pants image to ${remote_tag}"
fi
