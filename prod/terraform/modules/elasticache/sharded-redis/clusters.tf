# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  tags = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
}

resource "aws_elasticache_replication_group" "cluster" {
  for_each = var.shard_config

  description                 = "Redis cluster: ${var.base_cluster_name}-${each.key}"
  engine                      = "redis"
  node_type                   = each.value["node_type"]
  num_cache_clusters          = 1
  replication_group_id        = "${var.base_cluster_name}-shard-${each.key}"
  parameter_group_name        = var.param_group_name
  port                        = var.redis_port
  preferred_cache_cluster_azs = [each.value["az"]]
  security_group_ids          = [aws_security_group.redis.id]
  subnet_group_name           = aws_elasticache_subnet_group.redis_subnet_group.name
  tags                        = local.tags
  at_rest_encryption_enabled  = true
}

output "redis_endpoints" {
  value = { for shard_key, shard in aws_elasticache_replication_group.cluster : shard_key => shard.primary_endpoint_address }
}
