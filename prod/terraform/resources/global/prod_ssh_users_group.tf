# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# IAM group for users allowed to ssh into prod machines.

resource "aws_iam_group" "prod_ssh_users" {
  name = "prod_ssh_users"
}

