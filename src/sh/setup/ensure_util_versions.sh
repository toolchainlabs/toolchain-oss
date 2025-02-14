#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

arch="$(uname -s)"
tool_versions_dir=".tool_versions/${arch}"
mkdir -p "${tool_versions_dir}"

missing=0

function semver() {
  ./src/sh/setup/semver.py "$1" "$2"
}

function sum_md5() {
  ./src/sh/setup/md5.py "$@"
}

# Check that a version of a binary matches a semver condition.
function check() {
  binary=$1
  semver_condition=$2
  version_func=$3

  binary_path=$(command -v "${binary}" || true)
  if [ "${binary_path}" = "" ]; then
    echo "$(tput setaf 1)${binary} not found.$(tput sgr0)"
    missing=1
    return
  fi

  # md5-ing the tool binary is much faster that running it to extract its version,
  # so we store the expected hashes (along with the semver condition) and only run the slow version
  # extraction if either the hash or the semver condition has changed.
  hash_file="${tool_versions_dir}/${binary}"
  expected_tool_hash="${semver_condition} $(sum_md5 "${binary_path}")"

  if [ -e "${hash_file}" ]; then
    recorded_tool_hash="$(cat "${hash_file}")"
    if [ "${recorded_tool_hash}" = "${expected_tool_hash}" ]; then
      return
    fi
  fi

  version=$(${version_func} 2>&1)

  if [[ "${version}" == "" ]]; then
    # We failed to find a version and already reported that the binary wasn't found, so just return.
    return
  fi

  if ! semver "${version}" "${semver_condition}" &> /dev/null; then
    echo -e "$(tput setaf 1)${binary} version ${version} does not match expected semver condition '${semver_condition}'$(tput sgr0)"
    missing=1
  else
    echo -e "$(tput setaf 2)${binary} version ${version} matches expected semver condition '${semver_condition}'$(tput sgr0)"
    echo -e "${expected_tool_hash}" > "${tool_versions_dir}/${binary}"
  fi
}

# Each binary has its own representation of a version string. Turning those into semvers requires
# individual munging logic. So each of these functions applies such logic to the version string
# emitted by one specific binary.
# They each take one argument - the semver condition to check.

function check_jq() {
  function jq_version_func {
    jq --version | cut -c 4-
  }
  check "jq" "$1" jq_version_func
}

function check_yq() {
  function yq_version_func {
    yq --version 2>&1 | grep -o --extended-regexp "\\d+\\.\\d+\\.\\d+" | head -n 1
  }
  check "yq" "$1" yq_version_func
}

function check_pyenv() {
  function pyenv_version_func {
    pyenv --version | awk '{print $2}'
  }
  check "pyenv" "$1" pyenv_version_func
}

function check_postgres() {
  function postgres_version_func {
    postgres --version | awk '{print $3}'
  }
  check "postgres" "$1" postgres_version_func
}

function check_aws() {
  function aws_version_func {
    aws --version | grep -o --extended-regexp "\\d+\\.\\d+\\.\\d+" | head -n 1
  }
  check "aws" "$1" aws_version_func
}

function check_kubectl() {
  function kubectl_version_func {
    kubectl version --client=true -o json | jq -r '.clientVersion.gitVersion | ltrimstr("v")'
  }
  check "kubectl" "$1" kubectl_version_func
}

function check_helm() {
  function helm_version_func {
    helm version --template "{{.Version}}" | tr -d v
  }
  check "helm" "$1" helm_version_func
}

function check_terraform() {
  function terraform_version_func {
    terraform --version | grep -o --extended-regexp "\\d+\\.\\d+\\.\\d+" | head -n 1
  }
  check "terraform" "$1" terraform_version_func
}

function check_yarn() {
  function yarn_version_func {
    yarn --version
  }
  check "yarn" "$1" yarn_version_func
}

function check_aws_iam_authenticator() {
  function aws_iam_authenticator_version_func {
    version="$(aws-iam-authenticator version | jq -r '.Version | ltrimstr("v")')"
    if [[ "${version}" == "unversioned" ]]; then
      version="0.0.0"
    fi
    echo "${version}"
  }
  check "aws-iam-authenticator" "$1" aws_iam_authenticator_version_func
}

check_jq ">=1.6.0"
check_yq ">=4.25.3"
check_pyenv ">=2.3.11"
check_postgres ">=14.4"
check_aws ">=2.0.0"
check_kubectl ">=1.25.7"
check_helm ">=3.11.0"
check_terraform "=1.4.2"
check_yarn ">=0.22.19"
# aws-iam-authenticator may report its version as "unversioned", so we just check existence.
check_aws_iam_authenticator ">=0.0.0"

# TODO: Figure out how to check versions for the zlib and leveldb system libraries.

if [[ ${missing} -ne 0 ]]; then
  exit 1
fi
