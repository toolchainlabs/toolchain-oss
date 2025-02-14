# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket = "terraform.toolchainlabs.com"
    # TODO: rename key to state/us-east-1/elasticache/redis/remoting-prod-e1-1
    key            = "state/us-east-1/remoting/remoting-prod-e1-1"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  vpc_name = "remoting-prod-e1-1"
  common_tags = {
    Product = "remoting"
  }
}

data "aws_vpc" "remoting_prod_e1" {
  tags = {
    Name = local.vpc_name
  }
}