#!/usr/bin/env bash
# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

for name in $(git diff --staged --name-only); do
  # Funky way to test if file is binary.
  if [ -e "${name}" ] &&
    ! git merge-file /dev/null /dev/null "${name}" &> /dev/null &&
    ! git check-attr filter "${name}" | grep -q ' filter: lfs$'; then
    echo "Cannot commit binary file: ${name}"
    exit 1
  fi
done
