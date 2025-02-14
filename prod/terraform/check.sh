#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# a script to run various checks on our terraform config.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

cd prod/terraform/modules
terraform fmt -recursive -check -diff

cd ../resources
terraform fmt -recursive -check -diff
# NB: Must run init before validate.
./terraform_all.sh init
./terraform_all.sh validate
