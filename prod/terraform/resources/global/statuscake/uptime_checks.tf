# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global/statuscake/uptime"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "statuscake" {
  username = var.statuscake_username
  apikey   = var.statuscake_api_key
}

locals {
  status_codes = "204,205,206,303,400,401,403,404,405,406,408,410,413,444,429,494,495,496,499,500,501,502,503,504,505,506,507,508,509,510,511,521,522,523,524,520,598,599"
  locations = [
    "AU5",
    "BR1",
    "DUB2",
    "HRSM1",
    "IS1",
    "JP1",
    "PHO2",
    "SG2",
    "TORO3",
    "UG4",
    "ZA3",
    "usch2",
    "usda3"
  ]

  slack_cg      = "158307" # Slack & Email - https://app.statuscake.com/ContactGroup.php?CUID=158307
  pager_duty_cg = "217583" # PagerDuty https://app.statuscake.com/ContactGroup.php?CUID=217583
}

resource "statuscake_test" "infosite_check" {
  website_name     = "Infosite Prod uptime check"
  website_url      = "https://toolchain.com"
  test_type        = "HTTP"
  check_rate       = 60
  confirmations    = 2
  trigger_rate     = 0
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  contact_group    = [local.slack_cg]
}

resource "statuscake_test" "app_production_check" {
  website_name     = "App Production Uptime check."
  website_url      = "https://app.toolchain.com/healthz"
  test_type        = "HTTP"
  check_rate       = 60
  confirmations    = 3
  trigger_rate     = 3
  timeout          = 15
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  # We block access to app.toolchain.com from some countries using AWS WAF
  node_locations = local.locations
  contact_group  = [local.slack_cg, local.pager_duty_cg]
}

resource "statuscake_test" "app_staging_check" {
  website_name     = "App Staging Uptime check"
  website_url      = "https://staging.app.toolchain.com/healthz"
  test_type        = "HTTP"
  check_rate       = 300
  confirmations    = 2
  trigger_rate     = 3
  timeout          = 15
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  node_locations   = local.locations
  contact_group    = [local.slack_cg]
}

resource "statuscake_test" "cache_production_check" {
  website_name    = "Cache Production Uptime check"
  website_url     = "cache.toolchain.com"
  port            = 443
  test_type       = "TCP"
  check_rate      = 60
  confirmations   = 2
  trigger_rate    = 0
  timeout         = 15
  follow_redirect = true
  status_codes    = ""
  contact_group   = [local.slack_cg, local.pager_duty_cg]
}

resource "statuscake_test" "docs_check" {
  website_name     = "Docssite uptime check"
  website_url      = "https://docs.toolchain.com"
  test_type        = "HTTP"
  check_rate       = 60
  confirmations    = 5
  trigger_rate     = 0
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  contact_group    = [local.slack_cg]
}

resource "statuscake_test" "static_spa_assets_check" {
  website_name     = "Static assets (SPA) uptime check"
  website_url      = "https://assets.toolchain.com/health"
  test_type        = "HTTP"
  check_rate       = 60
  confirmations    = 2
  trigger_rate     = 0
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  contact_group    = [local.slack_cg, local.pager_duty_cg]
}

resource "statuscake_test" "static_pants_demosite_assets_check" {
  website_name     = "Static assets (pants demo site) uptime check"
  website_url      = "assets.graphmyrepo.com/health"
  test_type        = "HTTP"
  check_rate       = 60
  confirmations    = 2
  trigger_rate     = 0
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  contact_group    = [local.slack_cg]
}

resource "statuscake_test" "pants_demosite_app_check" {
  website_name     = "Pants demo site (prod) uptime check"
  website_url      = "https://graphmyrepo.com/healthz"
  test_type        = "HTTP"
  check_rate       = 60
  confirmations    = 2
  trigger_rate     = 0
  enable_ssl_alert = true
  follow_redirect  = true
  status_codes     = local.status_codes
  contact_group    = [local.slack_cg]
}
