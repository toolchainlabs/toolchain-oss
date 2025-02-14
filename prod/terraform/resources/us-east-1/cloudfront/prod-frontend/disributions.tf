# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/cloudfront/prod-frontend"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_cloudfront_cache_policy" "managed_cache_optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_key_group" "source_maps_access" {
  name    = "source_maps_access"
  items   = [aws_cloudfront_public_key.source_maps.id]
  comment = "Used with cookies to control access to JS source maps"
}

resource "aws_cloudfront_public_key" "source_maps" {
  comment = "Public key for protecting access to source maps"
  # Private key is in AWS SecretsManager under: source_maps_keys (json w/ base64 encoded private key)
  encoded_key = file("source_maps_public_key.pem")
  name        = "source_map_public_key"
}

module "frontend_spa_distribution" {
  access_identity_id = "E26PRM311ZFB9X"
  source             = "../../../../modules/cloudfront"
  tag_cost_center    = "webapp"
  s3_bucket_name     = "assets.us-east-1.toolchain.com"
  s3_path            = "/prod/frontend/bundles"
  toolchain_env      = "production"
  custom_domain_zone = "toolchain.com"
  app_name           = "prod-frontend"
  protected_options = {
    enabled           = true
    path_pattern      = "*.map"
    cache_policy_id   = data.aws_cloudfront_cache_policy.managed_cache_optimized.id
    trusted_key_group = aws_cloudfront_key_group.source_maps_access.id
  }
}