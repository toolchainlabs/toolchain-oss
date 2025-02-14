# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global/route53"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  # Items in this dir are global and not tied to a region.
  # However the "aws" provider still requires that a valid region be specified.
  region = "us-east-1"
}

data "aws_region" "current" {}

data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}

data "aws_vpc" "remoting_prod" {
  tags = {
    Name = "remoting-prod-e1-1"
  }
}
