# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/kubernetes/remoting-prod-e1-1/nodes"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  common_tags = {
    Product = "remoting"
  }
}

data "terraform_remote_state" "remoting" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/remoting/remoting-prod-e1-1"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

locals {
  es_domain_names = ["prod-logging"]
}

data "aws_vpc" "main" {
  tags = {
    Name = "main"
  }
}

# See here for limits on number of IPs that can be allocated per instance:
# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html?shortFooter=true#AvailableIpPerENI
# This limits how many pods can run on a node (after holding back one IP for the instance itself).
#

module "service_nodes_group_v2" {
  source                  = "../../../../../modules/eks/node_groups"
  tag_cost_center         = "remoting"
  name                    = "service-nodes-v2"
  control_plane_state_key = "kubernetes/remoting-prod-e1-1/control_plane"
  instance_types          = ["m6i.large"]
  instance_category       = "service"
  availability_zones      = local.availability_zones
  desired_capacity        = 11
  min_size                = 3
  max_size                = 13
  can_access_all_dbs      = false
  extra_security_groups = [
    data.terraform_remote_state.remoting.outputs.can_access_sharded_redis_security_group_id,
  ]
  extra_tags = local.common_tags
}

