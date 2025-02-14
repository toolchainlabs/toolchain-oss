# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for a set of adjacent subnets.

# Data source for fetching attributes of the VPC for the subnet.
data "aws_vpc" "target" {
  id = var.vpc_id
}

# Data source that fetches attributes of available AZs.
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  # NB: Lists cannot be selected by the ternary operator, only scalars; thus, the hop through the
  # map here.
  az_key = length(var.availability_zones) == 0 ? "all_available" : "user_supplied"
  azs = {
    all_available = data.aws_availability_zones.available.names
    user_supplied = var.availability_zones
  }
}

# The subnet.
resource "aws_subnet" "main" {
  count = var.cardinality

  cidr_block              = cidrsubnet(data.aws_vpc.target.cidr_block, var.newbits, var.first_netnum + count.index)
  vpc_id                  = var.vpc_id
  availability_zone       = element(local.azs[local.az_key], count.index)
  map_public_ip_on_launch = var.map_public_ip

  tags = merge(var.tags, { Name = "${var.name}${var.cardinality == 1 ? "" : count.index}" })
}

# Give the subnet public routing, if requested.
resource "aws_route_table_association" "public" {
  count          = var.public_route_table_id != "" ? var.cardinality : 0
  subnet_id      = element(aws_subnet.main.*.id, count.index)
  route_table_id = var.public_route_table_id
}

# Give the subnet private routing, if requested.
resource "aws_route_table_association" "nat" {
  count          = var.nat_route_table_id != "" ? var.cardinality : 0
  subnet_id      = element(aws_subnet.main.*.id, count.index)
  route_table_id = var.nat_route_table_id
}

# Give the subnet local routing, if requested.
resource "aws_route_table_association" "local" {
  count          = var.local_route_table_id != "" ? var.cardinality : 0
  subnet_id      = element(aws_subnet.main.*.id, count.index)
  route_table_id = var.local_route_table_id
}

# The ids of the subnets.
output "ids" {
  value = aws_subnet.main.*.id
}

# A map from subnet ids to their availability zone names.
output "ids_to_azs" {
  value = zipmap(aws_subnet.main.*.id, aws_subnet.main.*.availability_zone)
}
