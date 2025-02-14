#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Needed for `RUN --mount` to work.
export DOCKER_BUILDKIT=1

echo "Build the Buildbox binaries and worker_scie image."

# Build worker binary into this directory.
./pants run src/python/toolchain/util/prod/rust_builder.py -- worker
cp dist/worker prod/docker/remoting/worker_scie/worker
mkdir -p dist/worker-scie/

docker build \
  --platform=linux/amd64 \
  -t "worker_scie:latest" \
  prod/docker/remoting/worker_scie

docker run -i --mount type=bind,source="$(pwd)/dist/worker-scie",target=/dist -t worker_scie:latest \
  cp /build/remote-workers /dist/
