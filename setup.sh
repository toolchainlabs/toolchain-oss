#!/usr/bin/env bash
# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

./src/sh/setup/ensure_env.sh
./src/sh/setup/ensure_git_lfs.sh
./src/sh/setup/setup_git_hooks.sh
./src/sh/setup/ensure_utils.sh
./src/sh/setup/helm_setup.sh
./src/sh/pants/pantsup.sh
