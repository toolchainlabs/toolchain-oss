# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/kubernetes/dev-e1-1/nodes"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  # For the dev cluster we restrict to just two AZs. This is because we run dev postgres databases on this cluster,
  # and they must be scheduled in the same AZ as their PersistentVolumeClaim. So we need to guarantee a robust number
  # of nodes in each AZ in which we can operate, and the easiest way to do this without a larger number of nodes
  # than we might otherwise need is to restrict the AZs.
  availability_zones = ["us-east-1a", "us-east-1b"]
  es_domain_names    = ["es-dev-1"]
}

data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}

data "aws_security_group" "can_access_redis" {
  vpc_id = data.aws_vpc.main.id
  name   = "can-access-dev-test-redis"
}

# See here for limits on number of IPs that can be allocated per instance:
# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html?shortFooter=true#AvailableIpPerENI
# This limits how many pods can run on a node (after holding back one IP for the instance itself).
# Nodes for general-purpose use (mostly serving endpoints).

module "workers_nodes_group" {
  source                  = "../../../../../modules/eks/node_groups"
  tag_cost_center         = "dev"
  name                    = "workers-nodes-group"
  control_plane_state_key = "kubernetes/dev-e1-1/control_plane"
  instance_category       = "worker"
  availability_zones      = local.availability_zones
  desired_capacity        = 4
  min_size                = 0
  max_size                = 10
  can_access_all_dbs      = false
  es_domain_names         = local.es_domain_names
  extra_security_groups   = [data.aws_security_group.can_access_redis.id]
  # https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html#managed-node-group-capacity-types-spot
  capacity_type    = "SPOT"
  instance_types   = ["t3a.xlarge", "m6i.xlarge", "c6i.xlarge"] # instance type w/ 4 vCPU and 16gb or 8gb memory
  root_volume_size = "200"
}

module "database_nodes_group" {
  source                  = "../../../../../modules/eks/node_groups"
  tag_cost_center         = "dev"
  name                    = "database-nodes-group"
  control_plane_state_key = "kubernetes/dev-e1-1/control_plane"
  instance_types          = ["m6i.large"]
  instance_category       = "database"
  availability_zones      = local.availability_zones
  desired_capacity        = 2
  min_size                = 0
  max_size                = 4
  can_access_all_dbs      = false
  es_domain_names         = local.es_domain_names # Needed due to logging (fluentbit)
}

module "service_nodes_group" {
  source                  = "../../../../../modules/eks/node_groups"
  tag_cost_center         = "dev"
  name                    = "service-nodes-group"
  control_plane_state_key = "kubernetes/dev-e1-1/control_plane"
  instance_types          = ["t3a.medium"]
  instance_category       = "service"
  availability_zones      = local.availability_zones
  desired_capacity        = 4
  min_size                = 0
  max_size                = 8
  can_access_all_dbs      = false
  es_domain_names         = local.es_domain_names
  extra_security_groups   = [data.aws_security_group.can_access_redis.id]
}
