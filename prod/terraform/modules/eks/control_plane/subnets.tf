# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Data source for fetching attributes of the VPC's public route table.
data "aws_route_table" "public" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "public"
  }
}

# Data source for fetching attributes of the VPC's private route table.
data "aws_route_table" "nat" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "nat"
  }
}

module "private_subnets" {
  source             = "../../vpc/subnets"
  cardinality        = 10
  vpc_id             = var.vpc_id
  first_netnum       = var.first_netnum
  name               = "${var.cluster_name}-private"
  map_public_ip      = false
  availability_zones = var.availability_zones
  tags = {
    "kubernetes.io/role/internal-elb"                          = "1"
    "kubernetes.io/cluster/${var.cluster_name}"                = "shared"
    "toolchain.com/cluster/subnet/${var.cluster_name}-private" = "1"
  }
  nat_route_table_id = data.aws_route_table.nat.id
}

module "public_subnets" {
  source             = "../../vpc/subnets"
  cardinality        = 10
  vpc_id             = var.vpc_id
  first_netnum       = var.first_netnum + 10
  name               = "${var.cluster_name}-public"
  map_public_ip      = true
  availability_zones = var.availability_zones
  tags = {
    "kubernetes.io/role/elb"                                  = "1"
    "kubernetes.io/cluster/${var.cluster_name}"               = "shared"
    "toolchain.com/cluster/subnet/${var.cluster_name}-public" = "1"
  }
  public_route_table_id = data.aws_route_table.public.id
}