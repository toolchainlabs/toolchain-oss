# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "terraform_remote_state" "global" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  region     = data.aws_region.current.name
  repo_root  = "${path.module}/../../../../../"
  tags       = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
  account_id = data.aws_caller_identity.current.account_id
}
