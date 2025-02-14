# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for load-balancing incoming web traffic.

# Data source to fetch the name of the AWS region we're operating in.
data "aws_region" "current" {}

locals {
  region                = data.aws_region.current.name
  logs_s3_bucket        = "logs.${local.region}.toolchain.com"
  access_logs_s3_bucket = coalesce(var.access_logs_s3_bucket, local.logs_s3_bucket)
}

# A security group for the load balancer.
resource "aws_security_group" "lb" {
  name        = "${var.name}-allow-lb-incoming"
  description = "Allow inbound HTTP/HTTPS traffic to the lb."
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Public subnets for the load balancer.
module "public_subnets" {
  source        = "../../../vpc/subnets"
  vpc_id        = var.vpc_id
  first_netnum  = var.first_netnum
  cardinality   = 3
  access        = "public"
  name          = "${var.name}-lb"
  map_public_ip = true
}

# The load balancer.
resource "aws_lb" "main" {
  name               = var.name
  load_balancer_type = "application"
  ip_address_type    = "ipv4"
  security_groups    = concat([aws_security_group.lb.id], var.extra_security_groups)
  subnets            = module.public_subnets.ids

  enable_deletion_protection = false # Otherwise terraform won't be able to destroy this if we ask it to!

  access_logs {
    bucket  = local.access_logs_s3_bucket
    prefix  = "elb-access-logs/${var.access_logs_prefix}"
    enabled = true
  }
}

# The target group to route HTTP traffic to.
resource "aws_lb_target_group" "main" {
  vpc_id   = var.vpc_id
  name     = var.name
  port     = 80
  protocol = "HTTP"
  health_check {
    port     = 80
    protocol = "HTTP"
    path     = "/healthz"
  }
}

# The listener for incoming HTTP traffic.
resource "aws_lb_listener" "front_end_http" {
  count             = var.enable_http ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_lb_target_group.main.arn
    type             = "forward"
  }
}

# Data source for fetching attributes of our ACM certificate.
data "aws_acm_certificate" "toolchain" {
  domain      = "toolchain.com"
  types       = ["AMAZON_ISSUED"]
  most_recent = true
}

# The listener for incoming HTTPS traffic.
resource "aws_lb_listener" "front_end_https" {
  count             = var.enable_https ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = data.aws_acm_certificate.toolchain.arn

  default_action {
    target_group_arn = aws_lb_target_group.main.arn
    type             = "forward"
  }
}

# The security group that allows backends to receive load balancer traffic.
resource "aws_security_group" "backend" {
  name        = "${var.name}-backend"
  description = "Allow all incoming traffic from load balancer to backends."
  vpc_id      = var.vpc_id

  ingress {
    security_groups = [aws_security_group.lb.id]
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    cidr_blocks     = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Data source that fetches attributes of the toolchain.com. hosted zone.
data "aws_route53_zone" "toolchain" {
  name = "toolchain.com."
}

resource "aws_route53_record" "elb" {
  zone_id = data.aws_route53_zone.toolchain.zone_id
  name    = "${var.name}.${data.aws_route53_zone.toolchain.name}"
  type    = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = false
  }
}

# The public dns name of the elb.
output "dns_name" {
  value = aws_route53_record.elb.name
}

# The ID of the backend security group.
output "backend_security_group_id" {
  value = aws_security_group.backend.id
}

# The ARN of the target group.
output "target_group_arn" {
  value = aws_lb_target_group.main.arn
}

output "http_listener_arn" {
  value = element(coalescelist(aws_lb_listener.front_end_http.*.arn, list("Module Configuration Error!")), 0)
}

output "https_listener_arn" {
  value = element(coalescelist(aws_lb_listener.front_end_https.*.arn, list("Module Configuration Error!")), 0)
}
