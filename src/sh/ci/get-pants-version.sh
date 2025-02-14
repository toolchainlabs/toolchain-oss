#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# returns the pants version w/o running pants. useful in CI to determine a CI cache key based on the pants version (instead of hasing pants.toml)
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# based on the pants script
PANTS_TOML=${PANTS_TOML:-pants.toml}

function get_pants_config_string_value {
  local config_key="$1"
  local optional_space="[[:space:]]*"
  local prefix="^${config_key}${optional_space}=${optional_space}"
  local raw_value
  raw_value="$(sed -ne "/${prefix}/ s|${prefix}||p" "${PANTS_TOML}")"
  local optional_suffix="${optional_space}(#.*)?$"
  echo "${raw_value}" |
    sed -E \
      -e "s|^'([^']*)'${optional_suffix}|\1|" \
      -e 's|^"([^"]*)"'"${optional_suffix}"'$|\1|' &&
    return 0
  return 0
}

get_pants_config_string_value 'pants_version'
