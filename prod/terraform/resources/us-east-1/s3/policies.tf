# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Allow load balancers to write access logs into the logs bucket,
# and allow the region's redshift account to write audit logs.

# Retrieves the attributes of the pre-existing elb service account for the region.
# Note that we do not create this account.
data "aws_elb_service_account" "main" {
}

resource "aws_s3_bucket_policy" "access_logs_write" {
  bucket = module.logs_bucket.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "billingreports.amazonaws.com"
        },
        Action = [
          "s3:GetBucketAcl",
          "s3:GetBucketPolicy"
        ],
        Resource = module.logs_bucket.arn
      },
      {
        Effect = "Allow",
        Principal = {
          Service = "billingreports.amazonaws.com"
        },
        Action   = "s3:PutObject",
        Resource = "${module.logs_bucket.arn}/*"
      },
      {
        Effect = "Allow",
        Principal = {
          AWS = data.aws_elb_service_account.main.arn
        },
        Action   = "s3:PutObject",
        Resource = "${module.logs_bucket.arn}/elb-access-logs/*",
      },
      {
        Effect = "Allow"
        Action = "s3:PutObject"
        Principal = {
          Service = "delivery.logs.amazonaws.com"
        },
        Resource = "${module.logs_bucket.arn}/elb-access-logs/*",
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect = "Allow"
        Principal = {
          Service = "delivery.logs.amazonaws.com"
        },
        Action   = "s3:GetBucketAcl",
        Resource = module.logs_bucket.arn,
      }
    ]
  })
}

resource "aws_cloudfront_origin_access_identity" "s3_access" {
  comment = "Identity used to access assets on s3 from cloudfront"
}

resource "aws_s3_bucket_policy" "cloudfront_access" {
  bucket = module.spa_assets_bucket.name
  policy = jsonencode(
    {
      Version = "2008-10-17",
      Id      = "Access assets from CloudFront",
      Statement = [
        {
          Effect = "Allow",
          Principal = {
            AWS = aws_cloudfront_origin_access_identity.s3_access.iam_arn
          },
          Action = "s3:GetObject",
          Resource = [
            "${module.spa_assets_bucket.arn}/prod/frontend/bundles/*",
            "${module.spa_assets_bucket.arn}/prod/pants-demo-site/bundles/*",
          ]
        }
      ]
    }
  )
}
