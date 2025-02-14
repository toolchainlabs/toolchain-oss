# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for bucket access policies.


locals {
  bucket_arn = "arn:aws:s3:::${local.bucket_name}"
}

# The policy that grants read-only access to the bucket.
resource "aws_iam_policy" "s3_readonly" {
  name        = "${local.bucket_name}-readonly"
  description = "Read-only access to s3 bucket ${local.bucket_name}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "s3:ListBucket",
            "s3:GetBucketAcl"
          ],
          Resource = "${local.bucket_arn}"
        },
        {
          Effect = "Allow",
          Action = [
            "s3:GetObject"
          ],
          Resource = "${local.bucket_arn}/*"
        }
      ]
    }
  )
}

# The policy that grants read and write access to the bucket.
resource "aws_iam_policy" "s3_readwrite" {
  name        = "${local.bucket_name}-readwrite"
  description = "Read/write access to s3 bucket ${local.bucket_name}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "s3:ListBucket",
            "s3:GetBucketAcl"
          ],
          Resource = local.bucket_arn
        },
        {
          Effect = "Allow",
          Action = [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject"
          ],
          Resource = "${local.bucket_arn}/*"
        }
      ]
    }
  )
}
