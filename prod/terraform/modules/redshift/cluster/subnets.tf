# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for the db's subnet group.


# Subnets for the cluster's subnet group.
module "redshift_subnet" {
  source       = "../../vpc/subnets"
  vpc_id       = var.vpc_id
  first_netnum = var.first_netnum
  cardinality  = 3
  access       = var.externally_accessible ? "public" : "local"
  name         = "redshift-${var.cluster_id}"
}

# Subnet group for the db host.
resource "aws_redshift_subnet_group" "main" {
  name       = var.cluster_id
  subnet_ids = module.redshift_subnet.ids
}
