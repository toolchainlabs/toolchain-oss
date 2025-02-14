#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/setup/homebrew_common.sh

# Setup a local install of homebrew at a pinned version. This gives us a fixed location for binaries, and is an easy way to
# get packages required the repo set up first time. This should be run very rarely and it will take ages.

rm -rf "${HOMEBREW_DIR}"
mkdir -p "${HOMEBREW_DIR}"
git clone git@github.com:Homebrew/brew.git "${HOMEBREW_DIR}"
git -C "${HOMEBREW_DIR}" checkout "${HOMEBREW_VERSION}"
# Install requirements from Brewfile.
$BREW upgrade # We must call `upgrade` before `bundle` due to https://github.com/Homebrew/homebrew-bundle/issues/751.
$BREW bundle install --verbose --file=3rdparty/homebrew/Brewfile
