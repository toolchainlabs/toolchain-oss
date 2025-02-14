# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# IAM group for users allowed to sudo on machines.
resource "aws_iam_group" "linux_sudo" {
  name = "linux_sudo"
}

# IAM group for users allowed to use docker on devboxes.
resource "aws_iam_group" "linux_docker" {
  name = "linux_docker"
}

