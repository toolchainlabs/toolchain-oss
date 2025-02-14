#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

for path in $1; do
  if [ -d "${path}" ]; then
    echo "Cache heavy hitters for ${path} in MB:"
    du --threshold=+128m -sm "${path}" | sort -rn
    echo
  fi
done
