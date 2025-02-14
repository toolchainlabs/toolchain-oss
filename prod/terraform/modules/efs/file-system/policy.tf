# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  region          = data.aws_region.current.name
  account_id      = data.aws_caller_identity.current.account_id
  file_systmem_id = aws_efs_file_system.cache_storage_fs.id
  file_system_arn = "arn:aws:elasticfilesystem:${local.region}:${local.account_id}:file-system/${local.file_systmem_id}"
}

resource "aws_iam_policy" "efs_access_policy" {
  name        = "${var.file_system_name}-access"
  description = "Access EFS ${var.file_system_name}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect   = "Allow",
          Action   = "ec2:DescribeAvailabilityZones",
          Resource = "*"
        },
        {
          Effect   = "Allow",
          Action   = "elasticfilesystem:CreateAccessPoint",
          Resource = local.file_system_arn,
          Condition = {
            StringLike = {
              "aws:RequestTag/efs.csi.aws.com/cluster" : "true"
            }
          }
        },
        {
          Effect = "Allow",
          Action = [
            "elasticfilesystem:DescribeMountTargets",
            "elasticfilesystem:DescribeAccessPoints",
            "elasticfilesystem:DescribeFileSystems"
          ],
          Resource = local.file_system_arn
        }
      ]
    }
  )
}
