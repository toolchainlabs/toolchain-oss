# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_iam_role" "copy_role" {
  name                  = "${var.cluster_id}-copy"
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

resource "aws_iam_role_policy_attachment" "copy_role" {
  count      = length(var.s3_copy_buckets)
  role       = aws_iam_role.copy_role.name
  policy_arn = "arn:aws:iam::${local.account_id}:policy/${var.s3_copy_buckets[count.index]}-readwrite"
}
