#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"


./pants package src/python/toolchain/buildsense/dynamodb_es_bridge:dynamodb-to-es-lambda
./pants run src/python/toolchain/prod/installs/install_buildsense_lambda.py
