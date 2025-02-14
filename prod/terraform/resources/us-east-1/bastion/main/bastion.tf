# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for the bastion host for this region's main VPC.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/bastion/main"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_route53_zone" "toolchain_private" {
  name         = "toolchain.private."
  private_zone = true
}

# Resources for the main bastion host for the main VPC for this region.
module "bastion" {
  source                  = "../../../../modules/vpc/bastion"
  vpc_name                = "main"
  availability_zone_index = 0
}

# Another bastion host in a different AZ, as backup.
# Uncomment this to create this bastion, if the main one is down for whatever reason.
# We don't (yet) need two bastions running permanently.
//module "bastion1" {
//  source = "../../../../modules/vpc/bastion"
//  vpc_id = "${data.aws_vpc.main.id}"
//  availability_zone_index = 1
//}

resource "aws_route53_record" "bastion" {
  zone_id = data.aws_route53_zone.toolchain_private.zone_id
  name    = "bastion.${data.aws_route53_zone.toolchain_private.name}"
  type    = "CNAME"
  ttl     = "300"
  records = [module.bastion.private_dns_name]
}

# The public dns name of the bastion host.
output "dns_name" {
  value = module.bastion.private_dns_name
}

# The public IP address of the bastion host.
output "public_ip" {
  value = module.bastion.public_ip
}