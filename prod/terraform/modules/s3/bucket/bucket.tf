# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_region" "current" {
}

locals {
  bucket_name = var.bucket_name == "" ? "${var.bucket_name_prefix}.${data.aws_region.current.name}.toolchain.com" : var.bucket_name
  tags        = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
}

resource "aws_s3_bucket" "main" {
  bucket = local.bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.main.bucket
  versioning_configuration {
    status = var.versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lifecycle" {
  count  = length(var.expiration_lifecycle_policies) > 0 ? 1 : 0
  bucket = aws_s3_bucket.main.bucket
  dynamic "rule" {
    for_each = var.expiration_lifecycle_policies
    content {
      id     = rule.key
      status = rule.value.enabled ? "Enabled" : "Disabled"
      expiration {
        days = rule.value.days
      }
      filter {
        prefix = rule.value.prefix
      }
    }
  }
}

resource "aws_s3_bucket_acl" "bucket_acl" {
  bucket = aws_s3_bucket.main.id
  acl    = "private"
}

output "name" {
  value = aws_s3_bucket.main.id
}

output "arn" {
  value = aws_s3_bucket.main.arn
}
