# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for one-per-region resources that are reused by
# all resources in this region.

module "infosite_prod_certificate" {
  source                    = "../../../modules/acm"
  hosted_zone               = "toolchain.com"
  domain_name               = "toolchain.com"
  subject_alternative_names = ["*.toolchain.com"]
}

module "infosite_staging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "staging.toolchain.com"
}

module "app_prod_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "app.toolchain.com"
}

module "app_staging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "staging.app.toolchain.com"
}

module "webhooks_prod_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "webhooks.toolchain.com"
}

module "webhooks_staging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "staging.webhooks.toolchain.com"
}

module "toolshed_prod_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchainlabs.com"
  domain_name = "toolshed.toolchainlabs.com"
}

module "toolshed_staging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchainlabs.com"
  domain_name = "staging.toolshed.toolchainlabs.com"
}

module "frontend_cdn_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "assets.toolchain.com"
}

module "remote_cache_prod_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "cache.toolchain.com"
}

module "remote_cache_staging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "staging.cache.toolchain.com"
}

module "prod_es_logging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchainlabs.com"
  domain_name = "logging.toolchainlabs.com"
}

module "dev_es_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchainlabs.com"
  domain_name = "dev-es.toolchainlabs.com"
}

module "graphmyrepo_certificate" {
  source                    = "../../../modules/acm"
  domain_name               = "graphmyrepo.com"
  hosted_zone               = "graphmyrepo.com"
  subject_alternative_names = ["*.graphmyrepo.com"]
}

module "staging_graphmyrepo_certificate" {
  source                    = "../../../modules/acm"
  domain_name               = "staging.graphmyrepo.com"
  hosted_zone               = "graphmyrepo.com"
  subject_alternative_names = ["*.staging.graphmyrepo.com"]
}

module "graphmyrepo_cdn_assets_certificate" {
  source      = "../../../modules/acm"
  domain_name = "assets.graphmyrepo.com"
  hosted_zone = "graphmyrepo.com"
}

module "remoting_edge_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "edge.toolchain.com"
}

module "remoting_workers_edge_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "edge.workers.toolchain.com"
}

module "remoting_workers_prod_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "workers.toolchain.com"
}
module "remoting_workers_staging_certificate" {
  source      = "../../../modules/acm"
  hosted_zone = "toolchain.com"
  domain_name = "staging.workers.toolchain.com"
}