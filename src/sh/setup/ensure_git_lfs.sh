#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

function semver() {
  ./src/sh/setup/semver.py "$1" "$2"
}

if ! command -v git-lfs &> /dev/null; then
  if [ "$(uname -sm)" = "Darwin x86_64" ]; then
    # Install in the systemwide homebrew instance (rather than the toolchain-specific one)
    # because that's also where git itself is used from.
    # TODO: Should we use git (and git-lfs) from the toolchain-specific homebrew dir?
    brew install git-lfs
  else
    # We don't want to sort through all the different ways to install git-lfs on various
    # linux flavors here, so we leave it to a human.
    echo "git-lfs not detected on your system. Please install it manually, then rerun this script."
    exit 1
  fi
fi

# Check git-lfs version to ensure it is not too old.
git_lfs_version="$(git lfs version | awk '{ print $1 }' | cut -f2 -d/)"
git_lfs_semver_condition='>=2.9.0'
if ! semver "${git_lfs_version}" "${git_lfs_semver_condition}"; then
  echo "git-lfs version ${git_lfs_version} does not meet condition: ${git_lfs_semver_condition}"
  echo "Please upgrade git-lfs."
  exit 1
fi

git_lfs_output=$(git lfs install 2>&1)
# We need to capture the output of the cmd and check its exit code, so we need to use $?.
# shellcheck disable=SC2181
if ! ([ $? == 0 ] || echo "${git_lfs_output}" | grep -q "Hook already exists: pre-push"); then
  echo "git lfs install error: ${git_lfs_output}"
  exit 1
fi

# When you first clone a repo, git-lfs is not yet set up in it, so the binary files aren't hydrated.
# So now that git-lfs is set up, we hydrate them manually one time.
git lfs pull
