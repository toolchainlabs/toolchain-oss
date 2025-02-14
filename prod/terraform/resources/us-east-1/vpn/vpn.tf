# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for the bastion host for this region's main VPC.

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/vpn"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}


# Retrieve the attributes of the main VPC for this region.
data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}
data "aws_route53_zone" "zone" {
  name = "toolchainlabs.com."
}

data "aws_security_group" "dev_elasticsearch" {
  vpc_id = data.aws_vpc.main.id
  name   = "can-access-es-dev-1-es"
}


data "aws_security_group" "prod_logging_elasticsearch" {
  vpc_id = data.aws_vpc.main.id
  name   = "can-access-prod-logging-es"
}

resource "aws_subnet" "vpn" {
  cidr_block              = "10.1.212.0/24"
  vpc_id                  = data.aws_vpc.main.id
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true
  tags = {
    "Name" = "vpn-subnet"
  }
}

resource "aws_security_group" "vpn_sg" {
  name        = "vpn-access-server"
  description = "For VPN Access Server"

  vpc_id = data.aws_vpc.main.id
  ingress {
    from_port   = 1194
    to_port     = 1194
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "vpn_host" {
  ami                         = "ami-00fe7cf9c33fe0cd4"
  instance_type               = "t2.small"
  subnet_id                   = aws_subnet.vpn.id
  vpc_security_group_ids      = [aws_security_group.vpn_sg.id, data.aws_security_group.dev_elasticsearch.id, data.aws_security_group.prod_logging_elasticsearch.id]
  associate_public_ip_address = true
  key_name                    = "vpn-ssh-keys"
  source_dest_check           = false
  tags = {
    "Name"                  = "vpn"
    "toolchain_cost_center" = "devops"
  }
  volume_tags = {
    Name                    = "vpn-root-volume"
    "toolchain_cost_center" = "devops"
  }
}

resource "aws_eip" "vpn_as_ip" {
  instance         = aws_instance.vpn_host.id
  public_ipv4_pool = "amazon"
  tags = {
    "Name"                  = "vpn_as_ip"
    "toolchain_cost_center" = "devops"
  }
}

resource "aws_route53_record" "vpn_dns" {

  name    = "tcvpn.toolchainlabs.com"
  type    = "A"
  zone_id = data.aws_route53_zone.zone.id
  records = [
    aws_eip.vpn_as_ip.public_ip
  ]
  ttl = 300
}
