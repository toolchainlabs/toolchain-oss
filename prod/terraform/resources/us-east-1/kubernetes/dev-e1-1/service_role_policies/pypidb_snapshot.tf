# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_iam_policy" "pypidb_snapshot_copier_policy" {
  name        = "pypidb_snapshot_copier"
  description = "Policy used by pypi_db_snapshot to copy pypi crawler data from prod to dev"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "rds:RestoreDBClusterFromSnapshot",
          "rds:CreateDBInstance",
          "rds:DescribeDBClusterSnapshots",
          "rds:DescribeDBInstances",
          "ec2:DescribeSecurityGroups",
          "rds:DescribeDBClusters"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "rds:ModifyDBCluster",
          "rds:DeleteDBCluster",
          "rds:DeleteDBInstance"
        ],
        Resource = [
          "arn:aws:s3:::pypi-dev.us-east-1.toolchain.com",
          "arn:aws:rds:*:${data.aws_caller_identity.current.account_id}:cluster:pypi-restore",
          "arn:aws:rds:*:${data.aws_caller_identity.current.account_id}:cluster-pg:pypi-restore",
          "arn:aws:rds:*:${data.aws_caller_identity.current.account_id}:cluster-snapshot:pypi-restore",
          "arn:aws:rds:*:${data.aws_caller_identity.current.account_id}:og:pypi-restore",
          "arn:aws:rds:*:${data.aws_caller_identity.current.account_id}:db:pypi-0-restore"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "s3:ListBucket",
          "s3:GetBucketAcl"
        ],
        Resource = "arn:aws:s3:::pypi-dev.us-east-1.toolchain.com"
      },
      {
        Effect   = "Allow",
        Action   = "s3:PutObject",
        Resource = "arn:aws:s3:::pypi-dev.us-east-1.toolchain.com/*"
      },
    ]
  })

}

resource "aws_iam_role" "pypidb_snapshot_copier" {
  name = "k8s.${local.cluster}.pypidb_snapshot_copier.job"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Action = "sts:AssumeRole",
          Principal = {
            AWS = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/k8s.${local.cluster}.nodes"]
          },
          Effect = "Allow"
        }
      ]
    }
  )
}


resource "aws_iam_role_policy_attachment" "pypidb_snapshot_copier_policies" {
  role       = aws_iam_role.pypidb_snapshot_copier.name
  policy_arn = aws_iam_policy.pypidb_snapshot_copier_policy.arn
}

