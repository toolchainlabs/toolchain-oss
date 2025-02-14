# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_route_table" "public" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "public"
  }
}

# Data source for fetching attributes of the VPC's local route table.
data "aws_route_table" "local" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "local"
  }
}

# Subnets for the ElasticSearch domain.
module "es_subnet" {
  source                = "../../vpc/subnets"
  vpc_id                = var.vpc_id
  first_netnum          = var.first_netnum
  cardinality           = var.az_count
  name                  = "${var.domain_name}-es"
  public_route_table_id = var.public_access ? data.aws_route_table.public.id : ""
  local_route_table_id  = var.local_access ? data.aws_route_table.local.id : ""
}

output "subnets_ids" {
  value = module.es_subnet.ids
}