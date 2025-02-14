# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for the bastion host for the remoting prod VPC.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/bastion/remoting-prod-e1-1"
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

module "bastion" {
  source                  = "../../../../modules/vpc/bastion"
  env_name                = "remoting-prod"
  vpc_name                = "remoting-prod-e1-1"
  availability_zone_index = 0
}

resource "aws_route53_record" "remoting_bastion" {
  zone_id = data.aws_route53_zone.toolchain_private.zone_id
  name    = "remoting-bastion.${data.aws_route53_zone.toolchain_private.name}"
  type    = "CNAME"
  ttl     = "300"
  records = [module.bastion.private_dns_name]
}

output "dns_name" {
  value = module.bastion.private_dns_name
}

output "public_ip" {
  value = module.bastion.public_ip
}