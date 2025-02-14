#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source src/sh/util/docker.sh

echo "Build the BuildBox remote exec worker image for Toolchain Labs."
remote_tag="${PRIVATE_IMAGE_REGISTRY:-}remoting/worker/toolchainlabs:${IMAGE_TAG:-dev}"

docker build \
  --platform=linux/amd64 \
  -t "${remote_tag}" \
  -f prod/docker/remoting/buildbox_run/Dockerfile.toolchainlabs \
  prod/docker/remoting/buildbox_run

if [ -z "${NO_PUSH:-}" ]; then
  debug "Pushing remote exec worker image for Toolchain Labs ..."
  ecr_login_private
  docker push "${remote_tag}"
  echo ""
  echo "Published new BuildBox remote exec worker image for Toolchain Labs: ${remote_tag}"
else
  echo ""
  echo "Tagged new BuildBox remote exec worker image for Toolchain Labs (NOT PUSHED): ${remote_tag}"
fi
