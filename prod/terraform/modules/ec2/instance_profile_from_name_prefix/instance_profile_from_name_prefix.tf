# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Data source to read remote state about global resources.
data "terraform_remote_state" "global" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

resource "random_id" "unique_name" {
  byte_length = 8
  prefix      = "${var.name_prefix}-"
}

locals {
  name = random_id.unique_name.hex
}

module "instance_profile" {
  source     = "../instance_profile"
  name       = local.name
  ssh_access = var.ssh_access
}

# The name of the instance profile.
output "name" {
  value = module.instance_profile.name
}

# The name of the role attached to the instance profile.
output "role_name" {
  value = module.instance_profile.role_name
}

# The ARN of the role attached to the instance profile.
output "role_arn" {
  value = module.instance_profile.role_arn
}
