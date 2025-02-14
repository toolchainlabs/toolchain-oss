# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Bucket for toolchain binaries, this bucket is not accessed by our SW (python/rust) so no need
# to create read-only/read-write policies like we do with other buckets.

data "aws_route53_zone" "toolchain_com" {
  name = "toolchain.com"
}

resource "aws_s3_bucket" "binaries_bucket" {
  bucket = "binaries.toolchain.com"
  tags = {
    toolchain_cost_center = "remoting"
  }
}

resource "aws_s3_bucket_acl" "binaries_bucket_acl" {
  bucket = aws_s3_bucket.binaries_bucket.id
  acl    = "public-read"
}

resource "aws_s3_bucket_website_configuration" "bianries_bucket_website" {
  bucket = aws_s3_bucket.binaries_bucket.id
  index_document {
    suffix = "index.html"
  }
}

resource "aws_route53_record" "binaries_subdomain" {
  zone_id = data.aws_route53_zone.toolchain_com.zone_id
  name    = "binaries.toolchain.com."
  type    = "A"
  alias {
    name                   = aws_s3_bucket.binaries_bucket.bucket_domain_name
    zone_id                = aws_s3_bucket.binaries_bucket.hosted_zone_id
    evaluate_target_health = true
  }
}