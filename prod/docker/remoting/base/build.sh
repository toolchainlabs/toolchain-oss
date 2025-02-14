#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Build base image used for executors."

source prod/docker/remoting/versions.sh

# Enable Docker BuildKit for nicer console UX.
export DOCKER_BUILDKIT=1

echo "Build the base image used for remoting."
docker build \
  --platform=linux/amd64 \
  -t executor_base_image:latest \
  --build-arg worker_base_image="$worker_base_image" \
  -f prod/docker/remoting/base/Dockerfile \
  prod/docker/remoting/base
