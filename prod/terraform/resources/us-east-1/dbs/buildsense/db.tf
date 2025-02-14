# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/dbs/buildsense"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
    encrypt        = true
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

module "buildsense_db" {
  source          = "../../../../modules/db/postgres_aurora"
  vpc_id          = data.aws_vpc.main.id
  name            = "buildsense"
  instance_class  = "db.t3.medium"
  first_netnum    = "60"
  tag_cost_center = "webapp"
}

output "host" {
  value = module.buildsense_db.host
}

output "port" {
  value = module.buildsense_db.port
}

output "can_access_db_security_group" {
  value = module.buildsense_db.can_access_db_security_group
}

