# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/s3"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

module "general_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "general"
  tag_cost_center    = "devops"
}

module "artifacts_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "artifacts"
  tag_cost_center    = "devops"
}

module "helm_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "helm"
  tag_cost_center    = "devops"
}

module "pypi_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "webapp"
  bucket_name_prefix = "pypi"
  expiration_lifecycle_policies = {
    "expire-modules-leveldb-input-lists" = {
      enabled = true
      prefix  = "prod/v1/modules/input_lists"
      days    = 14
      tags    = {}
    }
    "expire-modules-leveldb-data" = {
      enabled = true
      prefix  = "prod/v1/modules/leveldbs"
      days    = 15 # Staggered, so input_lists get deleted first
      tags    = {}
    }
    "expire-depgraph-leveldb-input-lists" = {
      enabled = true

      prefix = "prod/v1/depgraph/input_lists"
      days   = 14

    }
    "expire-depgraph-leveldb-data" = {
      enabled = true

      prefix = "prod/v1/depgraph/leveldbs"
      days   = 15 # Staggered, so input_lists get deleted first

    },
  }
}

module "pypi_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "dev"
  bucket_name_prefix = "pypi-dev"
  expiration_lifecycle_policies = {
    "expire-pypi-db-snapshots-dumps" = {
      enabled = true

      prefix = "shared/pypi_db_snapshots"
      days   = 10

    }
    "expire-modules-leveldb-input-lists" = {
      enabled = true

      prefix = "shared/modules/input_lists"
      days   = 34

    }
    "expire-modules-leveldb-data" = {
      enabled = true

      prefix = "shared/modules/leveldbs"
      days   = 35 # Staggered, so input_lists get deleted first

    }
    "expire-depgraph-leveldb-input-lists" = {
      enabled = true

      prefix = "shared/depgraph/input_lists"
      days   = 34

    }
    "expire-depgraph-leveldb-data" = {
      enabled = true

      prefix = "shared/depgraph/leveldbs"
      days   = 35 # Staggered, so input_lists get deleted first

    }
  }
}

module "maven_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "dev"
  bucket_name_prefix = "maven-dev"
}

module "buildsense_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "webapp"
  bucket_name_prefix = "builds.buildsense"
}

module "buildsense_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "dev"
  bucket_name_prefix = "staging.buildstats-dev"
}

module "logs_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "devops"
  bucket_name_prefix = "logs"
}

module "vagrant_box_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "remoting"
  bucket_name_prefix = "vagrant"
}

module "spa_assets_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "assets"
  tag_cost_center    = "webapp"
  versioning         = true
}

module "spa_assets_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "dev"
  bucket_name_prefix = "assets-dev"
  versioning         = true
}

module "scm_integration_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "scm-integration"
  tag_cost_center    = "webapp"
  versioning         = true
}

module "scm_integration_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "dev"
  bucket_name_prefix = "scm-integration-dev"
  versioning         = true
}

module "pants_demos_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "pants-demos"
  tag_cost_center    = "webapp"
  versioning         = true
}

module "pants_demos_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  tag_cost_center    = "dev"
  bucket_name_prefix = "pants-demos-dev"
  versioning         = true
}

module "bugout_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "bugout-dev"
  tag_cost_center    = "dev"
}

module "bugout_prod_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "bugout-prod"
  tag_cost_center    = "webapp"
}

module "email_dev_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "email-dev"
  tag_cost_center    = "dev"
}

module "email_prod_bucket" {
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "email-prod"
  tag_cost_center    = "webapp"
}

module "auth_token_mapping_dev_bucket" {
  source = "../../../modules/s3/bucket"
  # We can't have periods in the bucket name due to https://github.com/rustls/rustls/issues/184.
  bucket_name        = "auth-token-mapping-dev"
  bucket_name_prefix = "<ignored>"
  tag_cost_center    = "dev"
  versioning         = true
}

module "auth_token_mapping_prod_bucket" {
  source = "../../../modules/s3/bucket"
  # We can't have periods in the bucket name due to https://github.com/rustls/rustls/issues/184.
  bucket_name        = "auth-token-mapping-prod"
  bucket_name_prefix = "<ignored>"
  tag_cost_center    = "remoting"
  versioning         = true
}

module "binaries_bucket_deprecated" { # replaced by binaries_bucket defined in  binaries_bucket
  # Bucket used to publish TC binaries (only remote exec worker binaries for now)
  source             = "../../../modules/s3/bucket"
  bucket_name_prefix = "binaries"
  tag_cost_center    = "remoting"
}
