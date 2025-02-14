# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/efs/dev-e1-1/remote-storage"
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

module "dev_cache_storage_fs" {
  source           = "../../../../../modules/efs/file-system"
  file_system_name = "remote-cache-dev-file-system"
  vpc_id           = data.aws_vpc.main.id
  k8s_cluster_name = "dev-e1-1"
  tag_cost_center  = "dev"
  # Since we only create nodes in those AZs
  # see: kubernetes/dev-e1-1/nodes/nodes.tf
  availability_zones = ["us-east-1a", "us-east-1b"]
}