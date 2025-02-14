# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_iam_policy" "terraform_read_only" {
  name = "TerraformStateReadOnly"
}
