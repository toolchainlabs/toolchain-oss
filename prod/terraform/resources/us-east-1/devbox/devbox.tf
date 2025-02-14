# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resource for a machine devs can SSH into and perform resource-intensive tasks on, such as docker image builds.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/devbox"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

// Note: Providers used with import cannot depend on locals.
provider "aws" {
  region = "us-east-1"
}


data "aws_region" "current" {
}

# Retrieve the attributes of the main VPC for this region.
data "aws_vpc" "main" {
  tags = {
    Name = "main"
  }
}

module "devbox" {
  source         = "../../../modules/devbox"
  name           = "devbox"
  vpc_id         = data.aws_vpc.main.id
  data_volume_id = aws_ebs_volume.data.id
}

resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 1500 # 1.5TB
  iops              = 4500
  tags = {
    Name = "devbox-data"
  }
}

# The private IP address of the devbox.
output "private_dns_name" {
  value = module.devbox.private_dns_name
}

# The private IP address of the devbox.
output "private_ip" {
  value = module.devbox.private_ip
}
