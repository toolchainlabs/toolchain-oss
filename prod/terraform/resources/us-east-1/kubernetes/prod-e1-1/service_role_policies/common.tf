# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/kubernetes/prod-e1-1/service_role_policies"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  cluster    = "prod-e1-1"
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}

data "aws_eks_cluster" "cluster" {
  name = local.cluster
}

data "terraform_remote_state" "control_plane" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/${local.region}/kubernetes/${local.cluster}/control_plane"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

locals {
  oidc_provider     = data.terraform_remote_state.control_plane.outputs.oidc_provider
  oidc_provider_arn = data.terraform_remote_state.control_plane.outputs.oidc_provider_arn
}
