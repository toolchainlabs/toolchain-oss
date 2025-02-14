# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/kubernetes/remoting-prod-e1-1/control_plane"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_vpc" "remoting_prod" {
  tags = {
    Name = "remoting-prod-e1-1"
  }
}

locals {
  cluster_name = "remoting-prod-e1-1"
  vpc_id       = data.aws_vpc.remoting_prod.id

  # At the time of writing (Feb 2019) us-east-1e had no capacity, so we exclude it for now.
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1f"]

  common_tags = {
    Product = "remoting"
  }
}

module "control_plane" {
  source             = "../../../../../modules/eks/control_plane"
  tag_cost_center    = "remoting"
  cluster_name       = local.cluster_name
  vpc_id             = local.vpc_id
  first_netnum       = "100"
  availability_zones = local.availability_zones
  enable_logs        = true
  extra_tags         = local.common_tags
  has_ingress        = true
}

# Downstream configs expect a control plane (EKS or otherwise) to have these outputs.

output "cluster_name" {
  value = local.cluster_name
}

output "cluster_vpc_id" {
  value = local.vpc_id
}

output "control_plane_security_group_id" {
  value = module.control_plane.control_plane_security_group_id
}

output "oidc_provider" {
  value = module.control_plane.oidc_provider
}

output "oidc_provider_arn" {
  value = module.control_plane.oidc_provider_arn
}