# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_security_group" "can_access_redis" {
  name        = "can-access-${var.base_cluster_name}-redis"
  description = "Hosts allowed to connect to ${var.base_cluster_name}-redis clusters."
  vpc_id      = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "redis" {
  name        = var.base_cluster_name
  description = "Allow connections to remoting-sharded-redis."
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description     = "From can-access-${var.base_cluster_name}-redis"
    from_port       = var.redis_port
    to_port         = var.redis_port
    protocol        = "tcp"
    security_groups = [aws_security_group.can_access_redis.id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

output "can_access_redis_security_group_id" {
  value = aws_security_group.can_access_redis.id
}

output "redis_security_group_id" {
  value = aws_security_group.redis.id
}
