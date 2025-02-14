# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_security_group" "can_access_redis" {
  name        = "can-access-${var.cluster_name}-redis"
  description = "Hosts allowed to connect to ${var.cluster_name}."
  vpc_id      = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "redis" {
  name        = "${var.cluster_name}-redis"
  description = "Allow connections to ${var.cluster_name}."
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
  security_group_id        = aws_security_group.redis.id
  description              = "From can-access-redis"
  type                     = "ingress"
  from_port                = var.redis_port
  to_port                  = var.redis_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.can_access_redis.id
}

output "can_access_redis_security_group_id" {
  value = aws_security_group.can_access_redis.id
}

output "redis_security_group_id" {
  value = aws_security_group.redis.id
}
