# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_vpc" "vpc_with_vpn" {
  count = var.vpn_vpc_name == "" ? 0 : 1
  tags = {
    Name = var.vpn_vpc_name
  }
}

locals {
  vpn_vpc_id = var.vpn_vpc_name == "" ? aws_vpc.vpc.id : data.aws_vpc.vpc_with_vpn[0].id
}

data "aws_security_group" "vpn_security_group" {
  vpc_id = local.vpn_vpc_id
  name   = "vpn-access-server"
}

resource "aws_security_group" "bastion" {
  name        = "bastion-${var.name}"
  description = "Allow SSH to the bastion only when connected to VPN."
  vpc_id      = aws_vpc.vpc.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "access_bastion_from_vpn" {
  security_group_id        = aws_security_group.bastion.id
  description              = "From VPN Server"
  type                     = "ingress"
  protocol                 = "tcp"
  from_port                = 22
  to_port                  = 22
  source_security_group_id = data.aws_security_group.vpn_security_group.id
}

resource "aws_security_group" "from_bastion" {
  name        = "from_bastion"
  description = "Allow SSH from the bastion to hosts in this security group."
  vpc_id      = aws_vpc.vpc.id
  ingress {
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [aws_security_group.bastion.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

