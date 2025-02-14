# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  results_bucket = "artifacts.us-east-1.toolchain.com"
}

resource "aws_iam_policy" "remote_cache_usage_reporter_policy" {
  name        = "prod_remote_cache_usage_reporter_policy"
  description = "Policy used by remote cache usage reporter job."
  policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "s3:ListBucket",
            "s3:GetBucketAcl"
          ],
          Resource = "arn:aws:s3:::${local.results_bucket}"
        },
        {
          Effect   = "Allow",
          Action   = ["s3:PutObject", "s3:GetObject"],
          Resource = "arn:aws:s3:::${local.results_bucket}/prod/remote-cache*"
        },
        {
          Effect   = "Allow",
          Action   = ["elasticache:DescribeCacheClusters"],
          Resource = "arn:aws:elasticache:*:${data.aws_caller_identity.current.account_id}:cluster:*"
        },
      ]
  })
}

resource "aws_iam_role" "remote_cache_usage_reporter" {
  name = "k8s.${local.cluster}.remote-cache-usage-reporter.job"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = "sts:AssumeRole",
          Principal = {
            AWS = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/k8s.${local.cluster}.nodes"]
          }

        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "remote_cache_usage_reporter_policies" {
  role       = aws_iam_role.remote_cache_usage_reporter.name
  policy_arn = aws_iam_policy.remote_cache_usage_reporter_policy.arn
}
