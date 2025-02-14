# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for EC2 instances that act as Kubernetes nodes.

# Note that the control plane that manages these nodes can, but does not have to be, managed by EKS.

data "aws_region" "current" {}

locals {
  region = data.aws_region.current.name
}

data "terraform_remote_state" "control_plane" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/${local.region}/${var.control_plane_state_key}"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

locals {
  cluster_name   = data.terraform_remote_state.control_plane.outputs.cluster_name
  cluster_vpc_id = data.terraform_remote_state.control_plane.outputs.cluster_vpc_id
}

module "amis" {
  source = "../../ec2/amis"
}

data "aws_security_group" "nodes" {
  name = "k8s.${local.cluster_name}.nodes"
}

data "aws_subnets" "private_subnets" {
  filter {
    name   = "vpc-id"
    values = [local.cluster_vpc_id]
  }
  tags = { "toolchain.com/cluster/subnet/${local.cluster_name}-private" = "1" }
  dynamic "filter" {
    for_each = length(var.availability_zones) == 0 ? [] : ["dummy"]
    content {
      name   = "availabilityZone"
      values = var.availability_zones
    }
  }
}

data "aws_eks_cluster" "cluster" {
  name = local.cluster_name
}

module "userdata_base" {
  source = "../../ec2/userdata/base"
}

data "aws_security_group" "can_access_all_dbs" {
  count  = var.can_access_all_dbs ? 1 : 0
  vpc_id = local.cluster_vpc_id
  tags = {
    "toolchain.com/sg/can-access-all-dbs" = "1"
  }
}

data "aws_security_groups" "can_access_es" {
  count = length(var.es_domain_names) > 0 ? 1 : 0
  filter {
    name   = "group-name"
    values = formatlist("can-access-%s-es", var.es_domain_names)
  }
  filter {
    name   = "vpc-id"
    values = [local.cluster_vpc_id]
  }
}

locals {
  security_groups_ids = concat(
    [data.aws_security_group.nodes.id],
    data.aws_security_group.can_access_all_dbs.*.id,
    length(var.es_domain_names) > 0 ? data.aws_security_groups.can_access_es[0].ids : [],
    var.extra_security_groups,
  )
  node_labels = merge({
    "toolchain.instance_category" = var.instance_category,
  }, var.extra_node_labels)

  tags = merge(var.extra_tags,
    {
      toolchain_cost_center                         = var.tag_cost_center
      Name                                          = "${local.cluster_name}-${var.name}"
      "kubernetes.io/cluster/${local.cluster_name}" = "owned"
      "k8s.io/cluster-autoscaler/enabled" : var.cluster_autoscaler_tag
  })
}

data "aws_iam_role" "node_role" {
  name = "k8s.${local.cluster_name}.nodes"
}

resource "aws_launch_template" "main" {
  name_prefix            = "${local.cluster_name}-${var.name}-"
  vpc_security_group_ids = local.security_groups_ids
  key_name               = var.key_pair

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type           = "gp2"
      volume_size           = var.root_volume_size
      delete_on_termination = true
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags          = local.tags
  }
}

resource "aws_eks_node_group" "main" {
  cluster_name    = local.cluster_name
  node_group_name = "eks-cluster-ng-${local.cluster_name}-${var.name}"
  node_role_arn   = data.aws_iam_role.node_role.arn
  subnet_ids      = data.aws_subnets.private_subnets.ids
  labels          = local.node_labels
  capacity_type   = var.capacity_type
  instance_types  = var.instance_types
  scaling_config {
    desired_size = var.desired_capacity
    max_size     = var.max_size
    min_size     = var.min_size
  }
  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }
  tags = {
    toolchain_cost_center = var.tag_cost_center
  }
}