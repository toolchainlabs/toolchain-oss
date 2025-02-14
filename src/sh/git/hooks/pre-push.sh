#!/usr/bin/env bash
# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# git lfs installs its own pre-push hook, which we copy here so we don't have to deal with merging hook scripts.

command -v git-lfs > /dev/null 2>&1 || {
  printf >&2 "\nThis repository is configured for Git LFS but 'git-lfs' was not found on your path. If you no longer wish to use Git LFS, remove this hook by deleting .git/hooks/pre-push.\n"
  exit 2
}
git lfs pre-push "$@"
