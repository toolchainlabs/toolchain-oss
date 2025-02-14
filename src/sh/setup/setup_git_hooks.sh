#!/usr/bin/env bash
# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

pushd .git/hooks > /dev/null

# Note: the only one of these hooks that git-lfs uses is pre-push, and we've copied their hook
# into our custom one. git-lfs does also use the post-checkout, post-commit and post-merge
# hooks, which we don't set up here. But if you modify this script to set up any of those hooks,
# you'll need to copy git-lfs's hook into ours.
# Loop logic based on https://stackoverflow.com/a/59465676/38265
for hook_path in ../../src/sh/git/hooks/*.sh; do
  fn="${hook_path##*/}"
  hook=$(echo "$fn" | cut -d'.' -f 1)
  rm -f "${hook}"
  ln -s "${hook_path}" "${hook}"
done

popd > /dev/null
