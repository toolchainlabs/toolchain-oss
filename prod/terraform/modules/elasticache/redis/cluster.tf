# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  tags = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
}

resource "aws_elasticache_subnet_group" "redis_sg_group" {
  name       = "${var.cluster_name}-subnets"
  subnet_ids = module.ec_redis_subnet.ids
}

resource "aws_elasticache_replication_group" "redis" {
  automatic_failover_enabled = true
  engine                     = "redis"
  replication_group_id       = "${var.cluster_name}-rg-1"
  description                = var.description
  node_type                  = var.node_type
  parameter_group_name       = var.param_group_name
  engine_version             = "6.x"
  port                       = var.redis_port
  subnet_group_name          = aws_elasticache_subnet_group.redis_sg_group.name
  security_group_ids         = [aws_security_group.redis.id]
  at_rest_encryption_enabled = var.at_rest_encryption
  tags                       = local.tags
  num_cache_clusters         = var.number_cache_clusters
}


output "redis_primary_endpoint_address" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint_address" {
  value = aws_elasticache_replication_group.redis.reader_endpoint_address
}
