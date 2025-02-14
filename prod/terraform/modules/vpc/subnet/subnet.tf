# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for a single subnet.

module "subnet" {
  source = "../subnets"

  cardinality           = 1
  vpc_id                = var.vpc_id
  name                  = var.name
  availability_zones    = [var.availability_zone]
  newbits               = var.newbits
  first_netnum          = var.netnum
  map_public_ip         = var.map_public_ip
  public_route_table_id = var.public_route_table_id
  nat_route_table_id    = var.nat_route_table_id
  local_route_table_id  = var.local_route_table_id
}

locals {
  subnet_ids = keys(module.subnet.ids_to_azs)
}

# The id of the subnet.
output "id" {
  value = local.subnet_ids[0]
}
