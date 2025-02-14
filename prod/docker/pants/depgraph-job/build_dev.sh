#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail
IMAGE_TAG_PREFIX=dev ./prod/docker/pants/depgraph-job/build_helper.sh