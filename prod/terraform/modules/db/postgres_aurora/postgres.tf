# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for a postgres database host.


# Data source to fetch the name of the AWS region we're operating in.
data "aws_region" "current" {}

locals {
  region = data.aws_region.current.name
}


# Data source to fetch attributes of the role that provides RDS enhanced monitoring.
data "aws_iam_role" "rds_enhanced_monitoring" {
  name = "rds-enhanced-monitoring"
}

locals {
  cluster_id = replace(var.name, "_", "-")
  tags       = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
}


locals {
  # Note that these will appear in state in plaintext, so the password must be changed
  # as soon as the db is created.
  master_user             = "master"
  initial_master_password = "initial_master_pwd_change_me"
}


resource "aws_rds_cluster" "main" {
  engine                       = "aurora-postgresql"
  engine_mode                  = "provisioned"
  engine_version               = "14.4"
  cluster_identifier           = local.cluster_id
  deletion_protection          = true
  copy_tags_to_snapshot        = true
  master_username              = local.master_user
  master_password              = local.initial_master_password
  backup_retention_period      = 35
  preferred_backup_window      = "05:00-06:00"
  preferred_maintenance_window = "Tue:18:00-Tue:19:00" # 2pm-3pm EST, 11am-12pm PST
  vpc_security_group_ids       = [aws_security_group.db.id]
  db_subnet_group_name         = aws_db_subnet_group.main.name
  tags                         = local.tags
}


resource "aws_rds_cluster_instance" "main-instance" {
  engine             = "aurora-postgresql"
  count              = 1
  identifier         = "${local.cluster_id}-${count.index}"
  cluster_identifier = aws_rds_cluster.main.cluster_identifier
  instance_class     = var.instance_class
  tags               = local.tags
}


# The db host.
output "host" {
  value = aws_rds_cluster.main.endpoint
}

# The db port.
output "port" {
  value = aws_rds_cluster.main.port
}
