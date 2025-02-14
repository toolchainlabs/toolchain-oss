#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

source ./src/sh/db/username.sh

# The name of the database release may be provided as the first positional cmd-line arg.
# If not provided, the name will default to the name of the user running this script
# (or, to be precise, that user's expected name on the bastion host based on ssh config).

# The name of the Kubernetes namespace may be provided as the second positional cmd-line arg.
# If not provided, the namespace will default to the name of the release, as determined above.

username=$(get_username)
export RELEASE_NAME=${1-"${username}-db"}
export NAMESPACE=${2-${username}}
