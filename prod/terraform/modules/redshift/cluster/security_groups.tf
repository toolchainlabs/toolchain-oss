# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for the security groups that support accessing the db.

locals {
  # See https://docs.aws.amazon.com/quicksight/latest/user/regions.html.
  quicksight_ips = {
    "us-east-1" = "52.23.63.224/27"
    "us-east-2" = "52.15.247.160/27"
    "us-west-2" = "54.70.204.128/27"
  }
}

# Security group for hosts that can access the cluster.
resource "aws_security_group" "can_access_cluster" {
  name        = "can-access-redshift-${var.cluster_id}"
  description = "Hosts allowed to connect to ${var.cluster_id}."
  vpc_id      = var.vpc_id
}

data "aws_security_group" "can_access_all_dbs" {
  vpc_id = var.vpc_id
  tags = {
    "toolchain.com/sg/can-access-all-dbs" = "1"
  }
}

# Security group for the cluster hosts themselves.
resource "aws_security_group" "cluster" {
  name        = var.cluster_id
  description = "Allow connections to ${var.cluster_id}."
  vpc_id      = var.vpc_id

  ingress {
    from_port = local.port
    to_port   = local.port
    protocol  = "tcp"
    security_groups = [
      aws_security_group.can_access_cluster.id,
      data.aws_security_group.can_access_all_dbs.id
    ]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# A security group to allow qualified external access to the cluster.
resource "aws_security_group" "external_access" {
  count = var.externally_accessible ? 1 : 0

  name        = "${var.cluster_id}-external-access"
  description = "Allow access to the cluster from specific external IPs."
  vpc_id      = var.vpc_id

  # Allow access to the service port from AWS QuickSight.
  ingress {
    from_port   = local.port
    to_port     = local.port
    protocol    = "tcp"
    cidr_blocks = [lookup(local.quicksight_ips, local.region)]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "can_access_db_security_group" {
  value = aws_security_group.can_access_cluster.id
}
