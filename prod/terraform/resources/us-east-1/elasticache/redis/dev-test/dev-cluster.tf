# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/redis/temp-test"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}


data "aws_vpc" "main" {
  tags = {
    Name = "main"
  }
}

module "test_redis_sharded_dev" {
  source            = "../../../../../modules/elasticache/sharded-redis"
  tag_cost_center   = "dev"
  vpc_id            = data.aws_vpc.main.id
  base_cluster_name = "dev-test"
  description       = "dev test cluster"
  first_netnum      = 35
  shard_config = {
    alpha = {
      az        = "us-east-1a",
      node_type = "cache.t3.micro",
    },
    bravo = {
      az        = "us-east-1a",
      node_type = "cache.t3.micro",
    }
    charlie = {
      az        = "us-east-1a",
      node_type = "cache.t3.micro",
    }
  }
}

output "redis_endpoints" {
  value = module.test_redis_sharded_dev.redis_endpoints
}