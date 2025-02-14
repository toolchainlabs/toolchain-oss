#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A script to publish an updated chart to toolchain helm repo and install it to the production cluster.
# The updated docker image is typically built and pushed to ECR using `prod/docker/django/build.sh <service name>`.
# USE WITH CAUTION - THIS AFFECTS PRODUCTION!

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./src/python/toolchain/prod/installs/build_install_services_prod.py "$@"