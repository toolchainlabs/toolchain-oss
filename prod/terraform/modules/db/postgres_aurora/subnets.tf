# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Data source for fetching attributes of the VPC's local route table.
data "aws_route_table" "local" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "local"
  }
}

# Subnets for the db host's subnet group.
module "db_subnet" {
  source               = "../../vpc/subnets"
  vpc_id               = var.vpc_id
  first_netnum         = var.first_netnum
  cardinality          = 3
  name                 = "${var.name}-db"
  local_route_table_id = data.aws_route_table.local.id
}

# Subnet group for the db host.
resource "aws_db_subnet_group" "main" {
  name       = "${var.name}-db"
  subnet_ids = module.db_subnet.ids

  lifecycle {
    create_before_destroy = true
  }
}
