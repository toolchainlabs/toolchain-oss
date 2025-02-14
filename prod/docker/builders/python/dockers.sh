#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Runs arbitrary pants commands in a docker container set up for python builds.

# Usage notes:
# - The host's toolchain repo is mounted into the container.
# - However the workdir and distdir are set to .docker.pants.d and dist.docker respectively,
#   so they don't stomp on the host's dirs.
# - The bootstrap cache (~/.cache) is mounted from a volume, so it can persist between container runs.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/util/logging.sh

# A no-op run of this is fast (< 1 second warm), so might as well always run it, to ensure an up to date image.
./prod/docker/builders/python/build_builder_image.sh

bootstrap_cache=bootstrap_cache

if [[ -z $(docker volume ls -q --filter name=${bootstrap_cache}) ]]; then
  info "Creating volume ${bootstrap_cache}"
  docker volume create ${bootstrap_cache}
fi

docker run \
  --mount type=bind,source="$(pwd)",target=/toolchain/host_repo \
  --mount type=volume,src="${bootstrap_cache}",dst=/toolchain/.cache \
  --rm \
  pexbuild:latest "$@"
