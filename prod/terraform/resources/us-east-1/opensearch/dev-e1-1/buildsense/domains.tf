# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/elasticsearch/dev-e1-1/buildsense"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}
data "aws_region" "current" {}

data "aws_caller_identity" "current" {}


data "aws_iam_role" "cognito_es_role" {
  name = "CognitoAccessForAmazonES"
}


module "dev_es_identity_pool" {
  source                    = "../../../../../modules/cognito/identity_pool_for_es"
  user_pool_name            = "Toolchain-GoogleAuth"
  identity_pool_name        = "dev_kibana"
  authenticated_role_name   = "dev_kibana_auth_role"
  unauthenticated_role_name = "Cognito_KibanaUnauth_Role"
  es_domain_name            = local.domain_name
  client_id                 = "2sb3gf8n9ebdjrb30ag8panhvu"
}


locals {
  domain_name     = "es-dev-1"
  cluster_name    = "dev-e1-1"
  es_arn          = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${local.domain_name}/*"
  sts_arn_prefix  = "arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role"
  iam_role_prefix = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role"
  add_to_sg       = "k8s.${local.cluster_name}.nodes"
}


module "dev_es" {
  source          = "../../../../../modules/opensearch/domain"
  tag_cost_center = "dev"
  domain_name     = local.domain_name
  first_netnum    = 70
  vpc_id          = data.aws_vpc.main.id
  instance_type   = "c6g.2xlarge.search"
  instance_count  = 2
  ebs_size        = 50
  custom_domain   = "dev-es.toolchainlabs.com"
  extra_tags = {
    app = "buildsense-api"
    env = "toolchain_dev"
  }
  cognito_options = {
    enabled          = true
    user_pool_id     = module.dev_es_identity_pool.user_pool_id
    identity_pool_id = module.dev_es_identity_pool.identity_pool_id
    role_arn         = data.aws_iam_role.cognito_es_role.arn
  }
  access_policies = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.cluster_name}.buildsense-api.service" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.cluster_name}.buildsense-workflow.service" },
          Action    = ["es:ESHttpGet", "es:ESHttpHead"],
          Resource  = local.es_arn
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.cluster_name}.opensearch-dev-prox.service" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.cluster_name}.fluent-bit.service" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.cluster_name}.es-logging-curator.job" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.sts_arn_prefix}/dev-buildsense-dynamodb-to-es/dev-buildsense-dynamodb-to-es" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn
        }
      ]
    }
  )
}
