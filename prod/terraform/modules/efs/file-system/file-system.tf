# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_security_group" "cluster_nodes" {
  vpc_id = var.vpc_id
  name   = "k8s.${var.k8s_cluster_name}.nodes"
}

resource "aws_efs_file_system" "cache_storage_fs" {
  encrypted        = true
  performance_mode = "generalPurpose" # Should probbaly be maxIO
  throughput_mode  = "bursting"
  tags = {
    Name                  = var.file_system_name
    toolchain_cost_center = var.tag_cost_center
    kubernetes_cluster    = var.k8s_cluster_name
  }
}

resource "aws_security_group" "can_access_efs" {
  name        = "can-access-${var.file_system_name}"
  description = "Hosts allowed to connect to EFS ${var.file_system_name}"
  vpc_id      = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [data.aws_security_group.cluster_nodes.id]
    description     = "EFS access from ${var.k8s_cluster_name} nodes "
  }
}

# Based on https://stackoverflow.com/a/63728735/38265
# We first get all the subnets IDs in associated with the AZs passed to this module.
# Then we load actual subnet objects for those IDs.
# then we create availability_zone_subnets which maps AZ to subnet and making it so that we only
# select one subnet per AZ.
# Finally we use that to create the mount points (we are only allowed to create one mount point per AZ) 
data "aws_subnets" "private_subnets_ids" {
  tags = { "toolchain.com/cluster/subnet/${var.k8s_cluster_name}-private" = "1" }
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  filter {
    name   = "availabilityZone"
    values = var.availability_zones
  }
}

data "aws_subnet" "private" {
  for_each = toset(data.aws_subnets.private_subnets_ids.ids)
  id       = each.key
}

locals {
  availability_zone_subnets = {
    for s in data.aws_subnet.private : s.availability_zone => s.id...
  }
}

resource "aws_efs_mount_target" "mount" {
  for_each        = local.availability_zone_subnets
  file_system_id  = aws_efs_file_system.cache_storage_fs.id
  subnet_id       = each.value[1]
  security_groups = [aws_security_group.can_access_efs.id]
}

resource "aws_efs_access_point" "cache_storage" {
  file_system_id = aws_efs_file_system.cache_storage_fs.id
  posix_user {
    # The toolchain user id used in our docker container
    uid = 99
    gid = 99
  }
  root_directory {
    path = "/remote-cache"
    creation_info {
      # The toolchain user id used in our docker container
      owner_gid   = 99
      owner_uid   = 99
      permissions = 770 # rwxrwx--- user & group full access, public - no access.
    }
  }
}