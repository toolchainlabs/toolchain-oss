# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for one-per-region resources that are reused by
# all resources in this region.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/ecr"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

# ECR repositories not tied to specific Django-based services.
# The repositories for gunicorn images for Django services are created automatically by the
# src/python/toolchain/prod/ensure_service_setup.py script.

# An ECR repository for the images we use for CI jobs.
module "ci_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "ci"
}

module "ci_devops_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "ci-devops"
}

# An ECR repository for django-fronting nginx images in internal services
module "django_nginx_internal_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "django/nginx-internal"
}

# An ECR repository for django-fronting nginx images in external services (i.e. fronted by an AWS Load Balancer and facing the internet)
module "django_nginx_edge_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "django/nginx-edge"
}

module "redis_cli_tools_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "tools/redis-cli"
}

module "pants_demos_depgraph_job_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "pants-demos/depgraph-job"
}
