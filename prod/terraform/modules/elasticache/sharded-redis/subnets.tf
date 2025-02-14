# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Data source for fetching attributes of the VPC's local route table.
data "aws_route_table" "local" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "local"
  }
}

# Subnets for the redis cluster.
module "cache_subnets" {
  source               = "../../vpc/subnets"
  vpc_id               = var.vpc_id
  first_netnum         = var.first_netnum
  availability_zones   = var.availability_zones
  cardinality          = length(var.availability_zones)
  name                 = var.base_cluster_name
  local_route_table_id = data.aws_route_table.local.id
}

resource "aws_elasticache_subnet_group" "redis_subnet_group" {
  name       = "${var.base_cluster_name}-subnets"
  subnet_ids = module.cache_subnets.ids
}
