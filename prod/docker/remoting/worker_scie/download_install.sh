#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euox pipefail

COMPONENT=$1
COMMIT_SHA=$2
TEST_BINARY="${3:-}"

git clone --filter=tree:0 "https://gitlab.com/BuildGrid/buildbox/${COMPONENT}.git" "/tmp/${COMPONENT}"
cd "/tmp/${COMPONENT}"
git checkout "${COMMIT_SHA}"
cmake -B "/tmp/${COMPONENT}/build" "/tmp/${COMPONENT}" -DBUILD_TESTING=OFF &&
  make -C "/tmp/${COMPONENT}/build" install

make -C "/tmp/${COMPONENT}/build" install DESTDIR=/build
if [[ -n "${TEST_BINARY}" ]]; then
  sh -c "${COMPONENT} --help &> /dev/null"
fi
