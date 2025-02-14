#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

IMAGE_TAG="pants-demo-local-dev"

rm -f prod/docker/pants/depgraph-job/*.pex

./prod/docker/builders/python/dockers.sh  --no-watch-filesystem package src/python/toolchain/pants_demos/depgraph/job:pants-demo
cp dist.docker/src.python.toolchain.pants_demos.depgraph.job/pants-demo.pex prod/docker/pants/depgraph-job/

docker build --platform=linux/amd64 --file=prod/docker/pants/depgraph-job/Dockerfile prod/docker/pants/depgraph-job -t "${IMAGE_TAG}"

docker run -it  "${IMAGE_TAG}" --repo $1
