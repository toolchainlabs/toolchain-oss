#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# TODO: There is now a docker image for running local dynamob. Use that instead?

dynamodb_local_dir="${HOME}/dynamodb_local"
dynamodb_jar_path="${dynamodb_local_dir}/DynamoDBLocal.jar"

if [ ! -f "${dynamodb_jar_path}" ]; then
  mkdir -p "${dynamodb_local_dir}"
  dynamodb_tarball_path="${dynamodb_local_dir}/dynamodb_local_latest.tar.gz"
  curl -o "${dynamodb_tarball_path}" https://s3-us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz
  tar -x -C "${dynamodb_local_dir}" -f "${dynamodb_tarball_path}"
fi

dbpath=./.dev.dynamodb

mkdir -p "${dbpath}"

java \
  -Djava.library.path="${dynamodb_local_dir}/DynamoDBLocal_lib" \
  -jar "${dynamodb_jar_path}" \
  -dbPath "${dbpath}" \
  -port 4545
