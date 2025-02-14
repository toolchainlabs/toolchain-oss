# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_route_table" "local" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "local"
  }
}

# Subnets for the redis cluster.
module "ec_redis_subnet" {
  source               = "../../vpc/subnets"
  vpc_id               = var.vpc_id
  first_netnum         = var.first_netnum
  cardinality          = 2
  name                 = "${var.cluster_name}-redis"
  local_route_table_id = data.aws_route_table.local.id
}

output "subnets_ids" {
  value = module.ec_redis_subnet.ids
}