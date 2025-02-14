#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

source ./src/sh/db/username.sh

export INSTANCE_NAME=local-db

export DATADIR="${HOME}/toolchain.${INSTANCE_NAME}.pgsql"
