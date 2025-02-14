# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for one-per-region resources that are reused by
# all resources in this region.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/region"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_region" "current" {
}

# Our standard key pairs, for this region.
# See module source for key pair names and details. Key pairs can be referenced by name in other resources.
module "key_pairs" {
  source = "../../../modules/ec2/key_pairs"
}

# Our `toolchain-data` KMS key, for this region.
# Can be referenced by this alias in other resources.

locals {
  region        = data.aws_region.current.name
  data_key_name = "toolchain-data"
}

# The key we use for encrypting data at rest, e.g., in sqs.
module "data_key" {
  source = "../../../modules/kms/key"
  alias  = local.data_key_name
}
