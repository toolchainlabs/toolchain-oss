# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_route53_zone" "custom_domain_zone" {
  name         = "${var.custom_domain_zone}."
  private_zone = false
}
locals {
  origin_id     = "S3-${var.s3_bucket_name}${var.s3_path}"
  zone_id       = data.aws_route53_zone.custom_domain_zone.zone_id
  custom_domain = "assets.${var.custom_domain_zone}"
  tags = merge(var.extra_tags, {
    toolchain_cost_center = var.tag_cost_center, toolchain_env = var.toolchain_env
    toolchain_app_name    = var.app_name
  })
}

data "aws_acm_certificate" "custom_domain" {
  domain   = local.custom_domain
  statuses = ["ISSUED"]
}

data "aws_cloudfront_origin_access_identity" "s3_access" {
  id = var.access_identity_id
}

resource "aws_cloudfront_distribution" "distribution_from_s3" {
  enabled         = true
  is_ipv6_enabled = true
  price_class     = "PriceClass_100"
  aliases         = [local.custom_domain]
  tags            = local.tags

  origin {
    domain_name = "${var.s3_bucket_name}.s3.amazonaws.com"
    origin_id   = local.origin_id
    origin_path = var.s3_path
    s3_origin_config {
      origin_access_identity = data.aws_cloudfront_origin_access_identity.s3_access.cloudfront_access_identity_path
    }
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  default_cache_behavior {
    compress               = true
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.origin_id
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }
  }
  dynamic "ordered_cache_behavior" {
    for_each = var.protected_options.enabled ? [1] : []
    content {
      compress               = true
      default_ttl            = 0
      max_ttl                = 0
      path_pattern           = var.protected_options.path_pattern
      allowed_methods        = ["GET", "HEAD"]
      cached_methods         = ["GET", "HEAD"]
      target_origin_id       = local.origin_id
      viewer_protocol_policy = "https-only"
      cache_policy_id        = var.protected_options.cache_policy_id
      trusted_key_groups     = [var.protected_options.trusted_key_group]
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = false
    acm_certificate_arn            = data.aws_acm_certificate.custom_domain.arn
    ssl_support_method             = "sni-only"
    minimum_protocol_version       = "TLSv1.2_2019"
  }
}

resource "aws_route53_record" "custom_domain" {
  zone_id = local.zone_id
  name    = local.custom_domain
  type    = "CNAME"
  ttl     = "300"
  records = [aws_cloudfront_distribution.distribution_from_s3.domain_name]
}

resource "aws_s3_object" "health" {
  bucket        = var.s3_bucket_name
  key           = "${substr(var.s3_path, 1, -1)}/health"
  acl           = "public-read"
  force_destroy = true
  content_type  = "text/plain"
  content       = "all good"
}