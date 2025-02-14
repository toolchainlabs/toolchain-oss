#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Setup a local install of homebrew at a pinned version. This gives us a fixed location for binaries, and is an easy way to
# get packages required the repo set up first time. This should be run very rarely and it will take ages.

if (($# == 0)); then
  echo >&2 "Usage: $0 <Path to Toolchain Homebrew Install> "
  exit 1
fi

source ./src/sh/setup/homebrew_common.sh

# If the installed packages match what's expected then we're up to date.
if [ -e "${HOMEBREW_DIR}" ] && src/sh/setup/ensure_util_versions.sh; then
  exit 0
elif [ -n "${DISABLE_AUTO_HOMEBREW_BUILD-}" ]; then
  echo -e "\\033[31mPackage version mismatch(es) detected, install/upgrade using ${BREW}\\033[0m"
  exit 0
else
  echo -e "\\033[31mPackage version mismatch(es) detected, checking homebrew installation...\\033[0m"
fi

if [ -d "${HOMEBREW_DIR}" ]; then
  echo -e "\\033[31mThere is an existing homebrew installation, Please re-install homebrew requirments from a file using ./src/sh/setup/install_homebrew.sh\\033[0m"
else
  ./src/sh/setup/install_homebrew.sh
fi
