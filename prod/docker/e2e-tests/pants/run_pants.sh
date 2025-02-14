#!/bin/bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd ~/projects/minimal-pants
export PANTS_CONFIG_FILES="+['pants.e2e-tests.toml']"
./pants --version  # bootstrap plugins 
./pants test ::
ls -lah .pants.d/
cat .pants.d/pants.log
