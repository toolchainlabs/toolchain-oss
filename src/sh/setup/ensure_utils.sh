#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# TODO: On MacOS, ensure that our custom toolchain homebrew dir is first on the path, so we
# know that we have (specific versions of) these and others.

missing=0

function check() {
  binary=$1
  arg=$2
  if ! "${binary}" "${arg}" &> /dev/null; then
    echo "${binary} not found."
    missing=1
  fi
}

# Check binaries that have a --version flag.
for binary in aws terraform yq; do
  check ${binary} --version
done

# Check binaries that have a version subcommand.
for binary in kubectl helm; do
  check ${binary} --help
done

if [ ${missing} -ne 0 ]; then
  exit 1
fi
