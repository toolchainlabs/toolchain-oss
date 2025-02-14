# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resource for the region-wide user db shared by all projects.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/dbs/users"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_vpc" "main" {
  tags = {
    Name = "main"
  }
}

# The user db resources.
module "userdb" {
  source          = "../../../../modules/db/postgres_aurora"
  vpc_id          = data.aws_vpc.main.id
  name            = "users"
  instance_class  = "db.t3.medium"
  first_netnum    = "50"
  tag_cost_center = "webapp"
}

output "host" {
  value = module.userdb.host
}

output "port" {
  value = module.userdb.port
}

# The id of the security group that is allowed to access this db.
output "can_access_db_security_group" {
  value = module.userdb.can_access_db_security_group
}

