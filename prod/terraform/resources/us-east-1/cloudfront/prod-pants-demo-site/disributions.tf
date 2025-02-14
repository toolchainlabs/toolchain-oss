# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/cloudfront/prod-pants-demo-site"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

module "pants_demosite_spa_distribution" {
  access_identity_id = "E26PRM311ZFB9X"
  source             = "../../../../modules/cloudfront"
  tag_cost_center    = "webapp"
  s3_bucket_name     = "assets.us-east-1.toolchain.com"
  s3_path            = "/prod/pants-demo-site/bundles"
  toolchain_env      = "production"
  custom_domain_zone = "graphmyrepo.com"
  app_name           = "prod-pants-demo-site"
}
