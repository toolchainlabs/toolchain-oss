# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Create an isolated VPC in which to run the remote execution cluster (e.g., buildfarm). From a security standpoint, all resources for the
# buildfarm must be isolated from other Toolchain infrastructure since the cluster runs untrusted third-party code.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/vpc/remoting-prod-e1-1"
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

locals {
  vpc_name = "remoting-prod-e1-1"
}

module "vpc" {
  source          = "../../../../modules/vpc/vpc"
  name            = local.vpc_name
  base_cidr_block = module.vpc_constants.remoting_vpc_cidr_block
  vpn_vpc_name    = "main"
  vpc_tags = {
    Product = "remoting"
  }
}

data "aws_subnet" "private" {
  vpc_id = module.vpc.id
  filter {
    name   = "tag:Name"
    values = ["private"]
  }
}
