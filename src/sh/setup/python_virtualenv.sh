#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

PYTHON_MIN_VER=38
PYTHON_PEX_LOCK_FILE=3rdparty/python/default_toolchain.lock

# Create a python virtual env using the python version at PYTHON_BIN
# and keep it up to date with changes in requirements.txt.
# Short circuits if the env is already up to date.
# Note that this venv is not used by Pants, but it is used to run scripts etc.

if (($# == 0)); then
  echo >&2 "Usage: $0 <python binary>"
  echo >&2 "Eg: $0 /usr/bin/python3"
  echo >&2 "Eg: $0 /usr/bin/python3"
  exit 1
fi

PYTHON_BIN="$1"

python_ver() {
  local python="$1"
  "${python}" << EOF
import platform

print(''.join(platform.python_version_tuple()[:2]))
EOF
}

PYTHON_VER="$(python_ver "${PYTHON_BIN}")"
if ((PYTHON_VER < PYTHON_MIN_VER)); then
  echo >&2 "At minimum, a Python ${PYTHON_MIN_VER} interpreter is required."
  echo >&2 "Passed ${PYTHON_BIN} which is version ${PYTHON_VER}."
  exit 1
fi

arch="$(uname -s)"
PYTHON_VIRTUALENV=".venvs/${arch}/py${PYTHON_VER}"
mkdir -p "$(dirname "$PYTHON_VIRTUALENV")"

requirements_fingerprint() {
  git hash-object -t blob "${PYTHON_PEX_LOCK_FILE}"
}

python_abi() {
  local python="$1"
  "${python}" << EOF
import distutils.sysconfig
import distutils.util
import platform
import sys

impl = platform.python_implementation()  # EG: 'CPython'
ver = ''.join(platform.python_version_tuple()[:2])  # EG: '37'
malloc = 'm' if impl == 'CPython' and distutils.sysconfig.get_config_var('WITH_PYMALLOC') == 1 else ''
ucs = 'u' if sys.maxunicode > 2**16 else ''
plat = distutils.util.get_platform()  # EG: macosx-10.7-x86_64

print(f'{impl}{ver}{malloc}{ucs}-{plat}')
EOF
}

# Setup the Python virtual environment in the directory passed as $1.
setup_venv() {
  local venv_dir="$1"
  local venv_fingerprint_file="$2"
  set -x
  "${PYTHON_BIN}" -m venv "${venv_dir}" >&2
  local PIP="${venv_dir}/bin/pip"
  "${PIP}" install --upgrade "pip>=23.0.1"
  "${PIP}" install "pex==2.1.124"
  mkdir -p dist/
  rm -f dist/default_toolchain.json
  sed '/^\/\//d' "${PYTHON_PEX_LOCK_FILE}" > dist/default_toolchain.json # remove pants comments from lock file
  PEX_TOOLS=1 "${venv_dir}/bin/pex" --lock dist/default_toolchain.json --include-tools -- venv --pip --bin-path prepend --collisions-ok "${venv_dir}"
  rm dist/default_toolchain.json
  touch "${venv_dir}/${venv_fingerprint_file}"
  # Optionally install ipython. Django will use ipython by default if it is available,
  # this check prevents it from being forced on unsuspecting users.
  if [[ "${TOOLCHAIN_INSTALL_IPYTHON:-}" = "yes" ]]; then
    "${PIP}" install ipdb ipython==8.6.0 >&2
  fi
  set +x
}

PYTHON_ABI="$(python_abi "${PYTHON_BIN}")"
REQUIREMENTS_FINGERPRINT="$(requirements_fingerprint)"
FINGERPRINT_BASE_NAME=".fingerprint-${PYTHON_ABI}-${REQUIREMENTS_FINGERPRINT}"
VENV_FINGERPRINT_FILE="${PYTHON_VIRTUALENV}/${FINGERPRINT_BASE_NAME}"

if [ -e "${VENV_FINGERPRINT_FILE}" ]; then
  echo "${PYTHON_VIRTUALENV}"
  exit 0
fi

# Check whether we are on Linux and in a Virtualbox shared folder. We need to work around a long-standing bug
# in the Virtualbox shared folders driver that fails to delete files. This impacts pip installs particularly.
# See https://www.virtualbox.org/ticket/8761.
make_venv_in_tmp_dir=""
if [ "$(uname)" = "Linux" ]; then
  fstype="$(findmnt -J -T . | jq -r '.filesystems[0].fstype')"
  if [ "$fstype" = "vboxsf" ]; then
    make_venv_in_tmp_dir="1"
  fi
fi

# Set up a python virtual env, pip install current requirements, and tag the fingerprint of the installed requirements.
if [ -z "$make_venv_in_tmp_dir" ]; then
  rm -rf "${PYTHON_VIRTUALENV}"
  setup_venv "$PYTHON_VIRTUALENV" "$FINGERPRINT_BASE_NAME"
else
  # Work around the Virtualbox bug by creating the virtual environment in a temporary directory that is not
  # on the vboxsf filesystem.
  venv_tmp_dir="$(mktemp -t -d venvtmp.XXXXXX)"
  setup_venv "$venv_tmp_dir" "$FINGERPRINT_BASE_NAME"

  # Then move the virtual environment to the final location.
  rm -rf "${PYTHON_VIRTUALENV}"
  mv "$venv_tmp_dir" "${PYTHON_VIRTUALENV}"

  # And fix up the script shebang's to have the final `python` path.
  # shellcheck disable=SC2038,SC1117
  find "${PYTHON_VIRTUALENV}/bin" -type f -perm /111 | xargs \
    grep -l "^#\!${venv_tmp_dir}" | xargs \
    sed -i -e "1s@^#\!${venv_tmp_dir}@#\!${PYTHON_VIRTUALENV}@"
fi

echo "${PYTHON_VIRTUALENV}"
