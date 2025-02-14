# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/efs/remoting-prod-e1-1/remote-storage"
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

module "remoting_cache_storage_fs" {
  source           = "../../../../../modules/efs/file-system"
  file_system_name = "remoting-prod-e1-1-cache-file-system"
  vpc_id           = data.aws_vpc.remoting_prod.id
  k8s_cluster_name = "remoting-prod-e1-1"
  tag_cost_center  = "remoting"
  # Since we only create nodes in those AZs
  # see: kubernetes/remoting-prod-e1-1/nodes/nodes.tf
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
}