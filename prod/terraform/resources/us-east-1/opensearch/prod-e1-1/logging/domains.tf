# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/elasticsearch/prod-e1-1/logging"
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

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_iam_role" "cognito_es_role" {
  name = "CognitoAccessForAmazonES"
}


data "aws_vpc" "remoting_prod" {
  tags = {
    Name = "remoting-prod-e1-1"
  }
}

data "aws_security_group" "remoting_cluster_nodes" {
  vpc_id = data.aws_vpc.remoting_prod.id
  name   = "k8s.remoting-prod-e1-1.nodes"
}

data "aws_route_table" "remote_logging_peer" {
  vpc_id = data.aws_vpc.main.id
  tags = {
    "Name" = "remoting-logging"
  }
}

module "prod_logging_es_identity_pool" {
  source                    = "../../../../../modules/cognito/identity_pool_for_es"
  user_pool_name            = "Toolchain-GoogleAuth"
  identity_pool_name        = "logging_prod_kibana"
  authenticated_role_name   = "logging_prod_kibana_auth_role"
  unauthenticated_role_name = "Cognito_KibanaUnauth_Role"
  es_domain_name            = local.domain_name
  client_id                 = "1sj4ld8qc4o88qfhb0gc7cgr6u"
}

locals {
  domain_name      = "prod-logging"
  prod_cluster     = "prod-e1-1"
  remoting_cluster = "remoting-prod-e1-1"
  es_arn           = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${local.domain_name}/*"
  sts_arn_prefix   = "arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role"
  iam_role_prefix  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role"
}

module "prod_logging_es" {
  source          = "../../../../../modules/opensearch/domain"
  tag_cost_center = "devops"
  domain_name     = local.domain_name
  first_netnum    = 75
  vpc_id          = data.aws_vpc.main.id
  instance_type   = "c6g.xlarge.search"
  instance_count  = 3
  az_count        = 3
  ebs_size        = 256
  local_access    = false
  custom_domain   = "logging.toolchainlabs.com"
  extra_tags = {
    app = "logging"
    env = "toolchain_prod"
  }

  cognito_options = {
    enabled          = true
    user_pool_id     = module.prod_logging_es_identity_pool.user_pool_id
    identity_pool_id = module.prod_logging_es_identity_pool.identity_pool_id
    role_arn         = data.aws_iam_role.cognito_es_role.arn
  }
  access_policies = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.prod_cluster}.fluent-bit.service" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpPut"],
          Resource  = local.es_arn,
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.remoting_cluster}.fluent-bit.service" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpPut"],
          Resource  = local.es_arn,
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.prod_cluster}.es-logging-curator.job" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn,
        },
        {
          Effect    = "Allow",
          Principal = { AWS = "${local.iam_role_prefix}/k8s.${local.prod_cluster}.monitoring.grafana.service" },
          Action    = ["es:ESHttpGet", "es:ESHttpHead"],
          Resource  = local.es_arn,
        },
      ]
    }
  )
}

resource "aws_route_table_association" "peer" {
  count          = length(module.prod_logging_es.subnets_ids)
  subnet_id      = element(module.prod_logging_es.subnets_ids, count.index)
  route_table_id = data.aws_route_table.remote_logging_peer.id
}

resource "aws_security_group_rule" "ingress_from_remoting_cluster" {
  security_group_id        = module.prod_logging_es.es_security_group_id
  description              = "logging from remoting cluster"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = data.aws_security_group.remoting_cluster_nodes.id
}
