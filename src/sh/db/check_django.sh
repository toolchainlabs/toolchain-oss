#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Makes sure we can load django.

echo "Checking that django can load"
pants run src/python/toolchain/service/infosite:infosite-manage -- check
