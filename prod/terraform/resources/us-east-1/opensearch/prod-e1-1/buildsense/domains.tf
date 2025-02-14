# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/elasticsearch/prod-e1-1/buildsense"
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

locals {
  domain_name     = "prod-buildsense"
  cluster_name    = "prod-e1-1"
  es_arn          = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${local.domain_name}/*"
  sts_arn_prefix  = "arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role"
  iam_role_prefix = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role"
}

module "prod_buildsense_es" {
  source                   = "../../../../../modules/opensearch/domain"
  tag_cost_center          = "webapp"
  domain_name              = local.domain_name
  first_netnum             = 73
  ebs_size                 = 120
  vpc_id                   = data.aws_vpc.main.id
  instance_type            = "c6g.2xlarge.search"
  instance_count           = 2
  dedicated_master_enabled = true
  extra_tags = {
    app = "buildsense-api"
    env = "toolchain_prod"
  }

  access_policies = jsonencode(
    {
      "Version" : "2012-10-17",
      "Statement" : [
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
          Principal = { AWS = "${local.sts_arn_prefix}/prod-buildsense-dynamodb-to-es/prod-buildsense-dynamodb-to-es" },
          Action    = ["es:ESHttpPost", "es:ESHttpGet", "es:ESHttpHead", "es:ESHttpDelete", "es:ESHttpPut"],
          Resource  = local.es_arn
        }
      ]
    }
  )
}
