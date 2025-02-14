# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for ElasticSearch domain access policies.

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}


locals {
  region     = data.aws_region.current.name
  account_id = data.aws_caller_identity.current.account_id
  domain_arn = "arn:aws:es:${local.region}:${local.account_id}:domain/${var.domain_name}"
}


resource "aws_iam_policy" "elasticsearch_read_write_access_policy" {
  name        = "elasticsearch.${var.domain_name}.readwrite"
  description = "R/W Access to ES domain ${var.domain_name}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "es:ESHttpHead",
            "es:ESHttpGet",
            "es:ESHttpPost",
            "es:ESHttpPut",
            "es:ESHttpDelete"
          ],
          Resource = local.domain_arn
        }
      ]
    }
  )
}

resource "aws_iam_policy" "elasticsearch_readonly_access_policy" {
  name        = "elasticsearch.${var.domain_name}.readonly"
  description = "Read only access to ES domain ${var.domain_name}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {

          Effect = "Allow",
          Action = [
            "es:ESHttpHead",
            "es:ESHttpGet"
          ],
          Resource = local.domain_arn
        }
      ]
    }
  )
}

output "readwrite_policy_name" {
  value = aws_iam_policy.elasticsearch_read_write_access_policy.name
}

output "readonly_policy_name" {
  value = aws_iam_policy.elasticsearch_readonly_access_policy.name
}