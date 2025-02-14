#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Sets up virtualenvs for python3.
# If running on OSX sets up a local install of homebrew and uses the python packages installed there
# to construct the virtualenvs.
TOOLCHAIN_HOMEBREW="${HOME}/.toolchain/homebrew"

# Default to using system python.
PYTHON3="$(command -v python3)"

MACOS_PLATFORM_REGEX="Darwin (x86_64|arm64)"
# If we're on OSX, use homebrew to install packages and use the python binaries in TOOLCHAIN_HOMEBREW/
if [[ "$(uname -sm)" =~ $MACOS_PLATFORM_REGEX ]]; then
  # Check if user needs to install packages.
  ./src/sh/setup/homebrew_check.sh "${TOOLCHAIN_HOMEBREW}" >&2
  # Override python defaults.
  PY3_VERSION=3.9.12
  PYTHON3="${HOME}/.pyenv/versions/${PY3_VERSION}/bin/python"
  if [ ! -e "${PYTHON3}" ]; then
    "${TOOLCHAIN_HOMEBREW}/bin/pyenv" install "${PY3_VERSION}" >&2
  fi
fi

# TODO: We have complete control over prod linux python versions, since we install them in our docker images.
# However we should probably at least verify the major version of whatever Linux makes available to us.

# Setup python3 virtualenv
./src/sh/setup/python_virtualenv.sh "${PYTHON3}"
