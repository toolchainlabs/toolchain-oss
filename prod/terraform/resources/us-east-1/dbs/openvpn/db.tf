# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/dbs/openvpn"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_region" "current" {
}

data "aws_vpc" "main" {
  tags = {
    Name = "main"
  }
}

module "openvpn" {
  source          = "../../../../modules/db/mysql_aurora"
  vpc_id          = data.aws_vpc.main.id
  name            = "openvpn"
  instance_class  = "db.t3.small"
  first_netnum    = "44"
  tag_cost_center = "devops"
}

# The db's host.
output "host" {
  value = module.openvpn.host
}

# The db's port.
output "port" {
  value = module.openvpn.port
}

# The id of the security group that grants access to the db.
output "can_access_db_security_group" {
  value = module.openvpn.can_access_db_security_group
}
