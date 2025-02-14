#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/util/logging.sh
source ./src/sh/util/docker.sh

FULL_IMAGE_TAG="${IMAGE_TAG_PREFIX:-dev}-${IMAGE_TAG}"
debug "Building Pants Depgraph Demo image at rev ${FULL_IMAGE_TAG} ..."

rm -f prod/docker/pants/depgraph-job/*.pex

./prod/docker/builders/python/dockers.sh  --no-watch-filesystem package src/python/toolchain/pants_demos/depgraph/job:pants-demo
cp dist.docker/src.python.toolchain.pants_demos.depgraph.job/pants-demo.pex prod/docker/pants/depgraph-job/

remote_tag="${PRIVATE_IMAGE_REGISTRY:-}pants-demos/depgraph-job:${FULL_IMAGE_TAG}"
docker build --platform=linux/amd64 --file=prod/docker/pants/depgraph-job/Dockerfile prod/docker/pants/depgraph-job -t "${remote_tag}"


if [ -z "${NO_PUSH:-}" ]; then
  ecr_login_private

  debug "Pushing Pants Depgraph Demo image ..."
  docker push "${remote_tag}"

  info "Published new Pants Depgraph Demo image to ${remote_tag}"
else
  info "Would have published new Pants Depgraph Demo image to ${remote_tag}"
fi
