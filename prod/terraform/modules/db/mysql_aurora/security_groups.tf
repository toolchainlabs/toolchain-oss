# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Security group for hosts that can access the db.
resource "aws_security_group" "can_access_db" {
  name        = "can-access-${var.name}-db"
  description = "Hosts allowed to connect to ${var.name}."
  vpc_id      = var.vpc_id
}

data "aws_security_group" "can_access_all_dbs" {
  vpc_id = var.vpc_id
  tags = {
    "toolchain.com/sg/can-access-all-dbs" = "1"
  }
}

locals {
  ingress_sgs = [
    aws_security_group.can_access_db.id,
    data.aws_security_group.can_access_all_dbs.id
  ]
}

# Security group for the db hosts themselves.
resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "Allow connections to ${var.name}."
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = local.ingress_sgs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

output "can_access_db_security_group" {
  value = aws_security_group.can_access_db.id
}

output "db_security_group" {
  value = aws_security_group.db.id
}
