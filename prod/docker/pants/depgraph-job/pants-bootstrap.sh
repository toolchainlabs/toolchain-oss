#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# ***************************** TOOLCHAIN NOTE *************************************************************
# We want to bootstap pants when building the container rather then bootstapping it every time the container runs.
# So this script does that, and the script running in the container 
# will expect pants to be boostrapped and will fail if it is not there.
# This script is based on the pants script (github.com/pantsbuild/setup) with some modifications:
# * Doesn't run pants (only bootstraps it)
# * Can run from any folder, doesn't need to run from the build/repo root.
# * Doesn't try to detrmine pants version from a toml file (the pants version is passed as an argument)
# * Only support recent pants versions (2.5+) and only supports python 3.8 & 3.9
# * Doesn't try to detect pyenv and activate a pyenv version.
# * Removed a bunch of logic not needed in this context (bootstrapping pants into a docker container).
# * Remove VIRTUALENV_REQUIREMENTS that are not relevant for python 3.8 & 3.9
# * Remove the pex bootstrapped directory (created by bootstrap_pex)
# * Remove ~/.pex
# * Use pip w/ a --no-cache-dir directive
# ***********************************************************************************************************

set -eou pipefail


PYTHON_BIN_NAME="python3"
PANTS_BIN_NAME="${PANTS_BIN_NAME:-$0}"
PANTS_BOOTSTRAP="${HOME}/.cache/pants/setup/bootstrap-$(uname -s)-$(uname -m)"

PEX_VERSION=2.1.42
PEX_URL="https://github.com/pantsbuild/pex/releases/download/v${PEX_VERSION}/pex"
PEX_EXPECTED_SHA256="69d6b1b1009b00dd14a3a9f19b72cff818a713ca44b3186c9b12074b2a31e51f"

VIRTUALENV_VERSION=20.4.7
VIRTUALENV_REQUIREMENTS=$(
cat << EOF
virtualenv==${VIRTUALENV_VERSION} --hash sha256:2b0126166ea7c9c3661f5b8e06773d28f83322de7a3ff7d06f0aed18c9de6a76
filelock==3.0.12 --hash sha256:929b7d63ec5b7d6b71b0fa5ac14e030b3f70b75747cef1b10da9b879fef15836
six==1.16.0 --hash sha256:8abb2f1d86890a2dfb989f9a77cfcfd3e47c2a354b01111771326f8aa26e0254
distlib==0.3.2 --hash sha256:23e223426b28491b1ced97dc3bbe183027419dfc7982b4fa2f05d5f3ff10711c
appdirs==1.4.4 --hash sha256:a841dacd6b99318a741b166adb07e19ee71a274450e68237b4650ca1055ab128
zipp==3.4.1; python_version < "3.10" --hash sha256:51cb66cc54621609dd593d1787f286ee42a5c0adbb4b29abea5a63edc3e03098
EOF
)

COLOR_RED="\x1b[31m"
COLOR_GREEN="\x1b[32m"
COLOR_RESET="\x1b[0m"

function log() {
  echo -e "$@" 1>&2
}

function die() {
  (($# > 0)) && log "${COLOR_RED}$*${COLOR_RESET}"
  exit 1
}

function green() {
  (($# > 0)) && log "${COLOR_GREEN}$*${COLOR_RESET}"
}

function tempdir {
  mkdir -p "$1"
  mktemp -d "$1"/pants.XXXXXX
}

function get_exe_path_or_die {
  local exe="$1"
  if ! command -v "${exe}"; then
    die "Could not find ${exe}. Please ensure ${exe} is on your PATH."
  fi
}
 
function get_python_major_minor_version {
  local python_exe="$1"
  "$python_exe" <<EOF
import sys
major_minor_version = ''.join(str(version_num) for version_num in sys.version_info[0:2])
print(major_minor_version)
EOF
}

function set_supported_python_versions {
  # Python 3.9 only for this context.
  supported_python_versions_decimal=('3.9')
  supported_python_versions_int=('39')
  supported_message='3.9'
}

function check_python_exe_compatible_version {
  local python_exe="$1"
  local major_minor_version
  major_minor_version="$(get_python_major_minor_version "${python_exe}")"
  for valid_version in "${supported_python_versions_int[@]}"; do
    if [[ "${major_minor_version}" == "${valid_version}" ]]; then
      echo "${python_exe}" && return 0
    fi
  done
}

function determine_default_python_exe {
  for version in "${supported_python_versions_decimal[@]}" "3" ""; do
    local interpreter_path
    interpreter_path="$(command -v "python${version}")"
    if [[ -z "${interpreter_path}" ]]; then
      continue
    fi
    if [[ -n "$(check_python_exe_compatible_version "${interpreter_path}")" ]]; then
      echo "${interpreter_path}" && return 0
    fi
  done
}

function determine_python_exe {
  local pants_version="$1"
  set_supported_python_versions
  local requirement_str="For \`pants_version = \"${pants_version}\"\`, Pants requires Python ${supported_message} to run."
  local python_exe
  python_exe="$(get_exe_path_or_die "${PYTHON_BIN_NAME}")" || exit 1
  if [[ -z "$(check_python_exe_compatible_version "${python_exe}")" ]]; then
    die "Invalid Python interpreter version for ${python_exe}. ${requirement_str}"
  fi
  echo "${python_exe}"
}

function compute_sha256 {
  local python="$1"
  local path="$2"

  "$python" <<EOF
import hashlib

hasher = hashlib.sha256()
with open('${path}', 'rb') as fp:
    buf = fp.read()
    hasher.update(buf)
print(hasher.hexdigest())
EOF
}

function bootstrap_pex {
  local python="$1"
  local bootstrapped="${PANTS_BOOTSTRAP}/pex-${PEX_VERSION}/pex"
  if [[ ! -f "${bootstrapped}" ]]; then
    (
      green "Downloading the Pex PEX."
      mkdir -p "${PANTS_BOOTSTRAP}"
      local staging_dir
      staging_dir=$(tempdir "${PANTS_BOOTSTRAP}")
      cd "${staging_dir}"
      curl -LO "${PEX_URL}"
      fingerprint="$(compute_sha256 "${python}" "pex")"
      if [[ "${PEX_EXPECTED_SHA256}" != "${fingerprint}" ]]; then
        die "SHA256 of ${PEX_URL} is not as expected. Aborting."
      fi
      green "SHA256 fingerprint of ${PEX_URL} verified."
      mkdir -p "$(dirname "${bootstrapped}")"
      mv -f "${staging_dir}/pex" "${bootstrapped}"
      rmdir "${staging_dir}"
    ) 1>&2 || exit 1
  fi
  echo "${bootstrapped}"
}

function bootstrap_virtualenv {
  local python="$1"
  local bootstrapped="${PANTS_BOOTSTRAP}/virtualenv-${VIRTUALENV_VERSION}/virtualenv.pex"
  if [[ ! -f "${bootstrapped}" ]]; then
    (
      green "Creating the virtualenv PEX."
      pex_path="$(bootstrap_pex "${python}")" || exit 1
      mkdir -p "${PANTS_BOOTSTRAP}"
      local staging_dir
      staging_dir=$(tempdir "${PANTS_BOOTSTRAP}")
      cd "${staging_dir}"
      echo "${VIRTUALENV_REQUIREMENTS}" > requirements.txt
      "${python}" "${pex_path}" -r requirements.txt -c virtualenv -o virtualenv.pex
      mkdir -p "$(dirname "${bootstrapped}")"
      mv -f "${staging_dir}/virtualenv.pex" "${bootstrapped}"
      rm -rf "${staging_dir}"
    ) 1>&2 || exit 1
  fi
  echo "${bootstrapped}"
}

function bootstrap_pants {
  local pants_version="$1"
  local python="$2"
  local pants_sha="${3:-}"

  local pants_requirement="pantsbuild.pants==${pants_version}"
  local python_major_minor_version
  python_major_minor_version="$(get_python_major_minor_version "${python}")"
  local target_folder_name="${pants_version}_py${python_major_minor_version}"
  local bootstrapped="${PANTS_BOOTSTRAP}/${target_folder_name}"

  if [[ ! -d "${bootstrapped}" ]]; then
    (
      green "Bootstrapping Pants using ${python}"
      local staging_dir
      staging_dir=$(tempdir "${PANTS_BOOTSTRAP}")
      local virtualenv_path
      virtualenv_path="$(bootstrap_virtualenv "${python}")" || exit 1
      green "Installing ${pants_requirement} into a virtual environment at ${bootstrapped}"
      # shellcheck disable=SC2086
      "${python}" "${virtualenv_path}" --no-download "${staging_dir}/install" && \
      "${staging_dir}/install/bin/pip" install --no-cache-dir -U pip && \
      "${staging_dir}/install/bin/pip" install --no-cache-dir --progress-bar off "${pants_requirement}" && \
      ln -s "${staging_dir}/install" "${staging_dir}/${target_folder_name}" && \
      mv "${staging_dir}/${target_folder_name}" "${bootstrapped}" && \
      green "New virtual environment successfully created at ${bootstrapped}."
    ) 1>&2 || exit 1
  fi
  echo "${bootstrapped}"
}


pants_version=$1
python="$(determine_python_exe "${pants_version}")"
pants_dir="$(bootstrap_pants "${pants_version}" "${python}")" || exit 1

# Cleanup stuff that is no longer needed.
rm -rf ${PANTS_BOOTSTRAP}/pex*
rm -rf ${HOME}/.cache/pip
rm -rf ${HOME}/.pex
