# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/kubernetes/prod-e1-1/nodes"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}


locals {
  es_domain_names = ["prod-buildsense", "prod-logging"]
  # We currently have EBS volumes in those AZs (used by prometheus & influxdb) so we need to make sure
  # we have nodes in those zones so k8s can create pods and mount those volumes.
  availability_zones = ["us-east-1b", "us-east-1c", "us-east-1f"]
}
# See here for limits on number of IPs that can be allocated per instance:
# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html?shortFooter=true#AvailableIpPerENI
# This limits how many pods can run on a node (after holding back one IP for the instance itself).

# Nodes for general-purpose use (mostly serving endpoints).
# A m5.large can have up to 10 IP addresses * 3 NICs and so can run up to 29 pods.

module "service_nodes_group_v2" {
  source                  = "../../../../../modules/eks/node_groups"
  tag_cost_center         = "webapp"
  name                    = "service-nodes-v2"
  control_plane_state_key = "kubernetes/prod-e1-1/control_plane"
  instance_types          = ["m6i.large"]
  instance_category       = "service"
  availability_zones      = local.availability_zones
  desired_capacity        = 8
  min_size                = 1
  max_size                = 20
  can_access_all_dbs      = true
  es_domain_names         = local.es_domain_names
  root_volume_size        = 100
}

module "workers_nodes_group_v2" {
  source                  = "../../../../../modules/eks/node_groups"
  tag_cost_center         = "webapp"
  name                    = "workers-nodes-v2"
  control_plane_state_key = "kubernetes/prod-e1-1/control_plane"
  instance_types          = ["m6i.large"]
  instance_category       = "worker"
  availability_zones      = local.availability_zones
  desired_capacity        = 3
  min_size                = 1
  max_size                = 9
  can_access_all_dbs      = true
  es_domain_names         = local.es_domain_names
  root_volume_size        = 100
}
