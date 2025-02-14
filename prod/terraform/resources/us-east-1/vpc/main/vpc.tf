# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for this region's main VPC.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/vpc/main"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"

}

module "vpc_constants" {
  source = "../../../../modules/vpc/constants"
}
data "aws_caller_identity" "current" {}

# Resources of the main VPC for this region.
module "vpc" {
  source          = "../../../../modules/vpc/vpc"
  name            = "main"
  base_cidr_block = module.vpc_constants.main_vpc_cidr_block
  vpc_tags = {
    "kubernetes.io/cluster/dev-e1-1" = "shared"
  }
  enable_dynamodb_route = true
}