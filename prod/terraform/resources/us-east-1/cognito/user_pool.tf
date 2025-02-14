# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/cognito"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}
data "aws_region" "current" {}

data "aws_caller_identity" "current" {}


resource "aws_cognito_user_pool" "pool" {
  name = "Toolchain-GoogleAuth"
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "toolchain"
  user_pool_id = aws_cognito_user_pool.pool.id
}
