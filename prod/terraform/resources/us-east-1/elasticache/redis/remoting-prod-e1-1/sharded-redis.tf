# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  redis_port = 6379

  # Node type to use for each cluster.
  node_type = "cache.m6g.large"

  # Unique names and configuration for each of the shards.
  shard_config = {
    alpha = {
      az        = "us-east-1a",
      node_type = local.node_type,
    },
    bravo = {
      az        = "us-east-1b",
      node_type = local.node_type,
    },
    charlie = {
      az        = "us-east-1c",
      node_type = local.node_type,
    },
    delta = {
      az        = "us-east-1a",
      node_type = local.node_type,
    },
    echo = {
      az        = "us-east-1b",
      node_type = local.node_type,
    },
  }
}

resource "aws_elasticache_parameter_group" "storage_params_sharded" {
  family = "redis6.x"
  name   = "redis6x-lru-sharded"

  # Configure Redis to evict keys based on LRU strategy regardless of whether or not TTL is set.
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  # Configure increased sampling to improve LRU accuracy.
  parameter {
    name  = "maxmemory-samples"
    value = 10
  }
}

module "sharded_redis_cluster" {
  source            = "../../../../../modules/elasticache/sharded-redis"
  base_cluster_name = "remoting-prod-sharded"
  first_netnum      = 35
  tag_cost_center   = "remoting"
  vpc_id            = data.aws_vpc.remoting_prod_e1.id
  param_group_name  = aws_elasticache_parameter_group.storage_params_sharded.name
  shard_config      = local.shard_config
  description       = "remoting-prod-e1-1 sharded Redis storage"
  extra_tags        = local.common_tags
  redis_port        = local.redis_port
}

output "sharded_redis_endpoints" {
  value = module.sharded_redis_cluster.redis_endpoints
}

output "can_access_sharded_redis_security_group_id" {
  value = module.sharded_redis_cluster.can_access_redis_security_group_id
}
