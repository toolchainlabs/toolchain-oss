# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
  logs_bucket = "logs.${local.region}.toolchain.com"
}

# Data source to read remote state about global resources.
data "terraform_remote_state" "global" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

# Data source to read remote state about the crawler's one-per-region resources.
data "terraform_remote_state" "region" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/${local.region}/region"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

locals {
  master_user   = "master"
  user          = var.username
  readonly_user = "${local.user}_readonly"
  # Pwds must contain upper-case, lower-case and digit.
  initial_master_password = "In1tial_master_pwd_change_me"

  dbname       = var.username
  kms_key_name = "${var.cluster_id}-data"
  port         = 5439
}

# The key used to encrypt data in the cluster.
module "kms_key" {
  source = "../../kms/key"
  alias  = local.kms_key_name
}

# A role for cluster instances.
resource "aws_iam_role" "cluster_role" {
  name_prefix           = "${replace(var.cluster_id, "_", "-")}-role-"
  force_detach_policies = true

  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Action = "sts:AssumeRole",
          Principal = {
            Service = "redshift.amazonaws.com"
          },
          Effect = "Allow"
        }
      ]
    }
  )
}

# So we can log to the S3 bucket.
resource "aws_iam_role_policy_attachment" "logs_bucket_readwrite" {
  role       = aws_iam_role.cluster_role.name
  policy_arn = "arn:aws:iam::${local.account_id}:policy/${local.logs_bucket}-readwrite"
}

# Parameters for the cluster.
resource "aws_redshift_parameter_group" "main" {
  name        = "${replace(var.cluster_id, "_", "-")}-params"
  description = "Custom params for redshift cluster."
  family      = "redshift-1.0"

  parameter {
    name  = "require_ssl"
    value = "false"
  }

  parameter {
    name  = "enable_user_activity_logging"
    value = "true"
  }
}

# The cluster.
resource "aws_redshift_cluster" "main" {
  cluster_identifier           = var.cluster_id
  database_name                = "dev"
  master_username              = local.master_user
  master_password              = local.initial_master_password
  node_type                    = var.node_type
  cluster_type                 = var.multi_node ? "multi-node" : "single-node"
  cluster_subnet_group_name    = aws_redshift_subnet_group.main.name
  iam_roles                    = [aws_iam_role.copy_role.arn, aws_iam_role.cluster_role.arn]
  vpc_security_group_ids       = concat(aws_security_group.external_access.*.id, [aws_security_group.cluster.id])
  port                         = local.port
  publicly_accessible          = var.externally_accessible
  cluster_parameter_group_name = aws_redshift_parameter_group.main.name
  number_of_nodes              = 1
  encrypted                    = true
  kms_key_id                   = module.kms_key.arn # Not an error, this field expects an ARN despite the name.
  enhanced_vpc_routing         = true
  skip_final_snapshot          = true
  logging {
    enable        = true
    bucket_name   = local.logs_bucket
    s3_key_prefix = "redshift-audit-logs/${var.cluster_id}/"
  }
}

locals {
  host = aws_redshift_cluster.main.dns_name
}

# The cluster leader DNS name.
output "dns_name" {
  value = local.host
}

# The db port.
output "port" {
  value = aws_redshift_cluster.main.port
}
