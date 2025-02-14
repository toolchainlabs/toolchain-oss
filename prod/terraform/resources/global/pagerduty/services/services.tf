# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for one-per-region resources that are reused by
# all resources in this region.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global/pagerduty/services"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "pagerduty" {
  token = var.pagerduty_api_token
}

data "pagerduty_vendor" "statuscake" {
  name = "Statuscake"
}

module "toolchain_prod" {
  source              = "../../../../modules/pagerduty/services"
  service_name        = "toolchain_prod"
  service_description = "Toolchain Production"
  schedule_name       = "Toolchain Tier 1"
}

resource "pagerduty_service_integration" "statusckae" {
  name    = "statuscake"
  vendor  = data.pagerduty_vendor.statuscake.id
  service = module.toolchain_prod.service_id
}
