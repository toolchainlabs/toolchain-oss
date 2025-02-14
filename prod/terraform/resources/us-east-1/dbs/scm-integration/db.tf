# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/dbs/scm-integration"
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

module "scm_integration_db" {
  source          = "../../../../modules/db/postgres_aurora"
  tag_cost_center = "webapp"
  vpc_id          = data.aws_vpc.main.id
  name            = "scm-integration"
  instance_class  = "db.t3.medium"
  first_netnum    = "30"
}

# The db's host.
output "host" {
  value = module.scm_integration_db.host
}

# The db's port.
output "port" {
  value = module.scm_integration_db.port
}

# The id of the security group that grants access to the db.
output "can_access_db_security_group" {
  value = module.scm_integration_db.can_access_db_security_group
}
