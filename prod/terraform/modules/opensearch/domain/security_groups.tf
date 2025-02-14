# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Security group for hosts that can access the elasicsearch.

resource "aws_security_group" "can_access_es" {
  name        = "can-access-${var.domain_name}-es"
  description = "Hosts allowed to connect to ${var.domain_name}."
  vpc_id      = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "es" {
  name        = "${var.domain_name}-es"
  description = "Allow connections to ${var.domain_name}."
  vpc_id      = var.vpc_id


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
resource "aws_security_group_rule" "ingress_from_can_access_es" {
  security_group_id        = aws_security_group.es.id
  description              = "From can-access-es"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.can_access_es.id
}


output "can_access_es_security_group_id" {
  value = aws_security_group.can_access_es.id
}

output "es_security_group_id" {
  value = aws_security_group.es.id
}