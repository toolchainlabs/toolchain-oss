# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for one-per-region resources that are reused by
# all resources in this region.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/waf"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_wafv2_ip_set" "bad_ips" {
  name               = "bad-ips"
  description        = "IP Addresses that are crawling our site looking for vulnerabilities"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  # IPs that are from countries we don't want to block (US/EU) but we get unwanted traffic from.
  # It is safe to remove IPs from this list from time to time (as they become stale)
  addresses = [
    "150.136.75.66/32",
    "172.105.13.165/32",
    "104.236.58.24/32",
  ]
}


resource "aws_wafv2_web_acl" "servicerouter" {
  name        = "servicerouter"
  description = "Web ACL for the main app ALB app.toolchain.com"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "block-countries"
    priority = 1
    action {
      block {}
    }
    statement {
      geo_match_statement {
        country_codes = [
          "CN", # China
          "RU", # Russia
          "IR", # Iran
        ]
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "block-countries"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "block-ips"
    priority = 2
    action {
      block {}
    }
    statement {
      ip_set_reference_statement {
        arn = aws_wafv2_ip_set.bad_ips.arn
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "block-ips"
      sampled_requests_enabled   = true
    }
  }

  tags = {
    tc_env = "prod"
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "acl-metric"
    sampled_requests_enabled   = true
  }
}
