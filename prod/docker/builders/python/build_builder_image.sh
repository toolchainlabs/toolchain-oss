#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Note: Builds a docker image that itself can build pexes.
# To run a container from this image and build pexes, see build_pex.sh in this dir.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

my_host_uid=$(id -u)

# Bake the current user's host uid into the image so that the builder container can write to the host's
# workdir. Note that this is only OK to do because this is a local helper image used in building,
# and we never push it anywhere.
docker build  --platform=linux/amd64 -t pexbuild --build-arg toolchain_user_uid="${my_host_uid}" prod/docker/builders/python/builder_image
