# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for load-balancing incoming web traffic.

# Note that, unlike application load balancers, network load balancers don't support security groups.
# The backend instances must use IP addresses to allow traffic from the load balancer.
# See https://docs.aws.amazon.com/elasticloadbalancing/latest/network/target-group-register-targets.html#target-security-groups.

# Data source to fetch the name of the AWS region we're operating in.
data "aws_region" "current" {}

locals {
  region                = data.aws_region.current.name
  logs_s3_bucket        = "logs.${local.region}.toolchain.com"
  access_logs_s3_bucket = coalesce(var.access_logs_s3_bucket, local.logs_s3_bucket)
  num_public_subnets    = 3
  ports_set             = toset([for port in var.ports : tostring(port)])
}

# Data source for fetching attributes of the VPC's public route table.
data "aws_route_table" "public" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "public"
  }
}

# Public subnets for the load balancer.
module "public_subnets" {
  source        = "../../../vpc/subnets"
  cardinality   = local.num_public_subnets
  vpc_id        = var.vpc_id
  first_netnum  = var.first_netnum
  name          = "${var.name}-lb"
  map_public_ip = true

  public_route_table_id = data.aws_route_table.public.id
}

# The load balancer.
resource "aws_lb" "main" {
  name               = var.name
  load_balancer_type = "network"
  ip_address_type    = "ipv4"
  subnets            = module.public_subnets.ids

  enable_deletion_protection = false # Otherwise terraform won't be able to destroy this if we ask it to!

  access_logs {
    bucket  = local.access_logs_s3_bucket
    prefix  = "elb-access-logs/${var.access_logs_prefix}"
    enabled = !var.disable_access_logs
  }

  tags = var.extra_tags
}

# Create a target group for each forwarded port.
resource "aws_lb_target_group" "main" {
  for_each = local.ports_set

  vpc_id      = var.vpc_id
  name        = "${var.name}-tg-port${each.value}"
  port        = each.value
  protocol    = "TCP"
  target_type = "instance"

  lifecycle {
    create_before_destroy = true
  }

  tags = var.extra_tags
}

# The listener for incoming traffic.
resource "aws_lb_listener" "front_end" {
  for_each = local.ports_set

  load_balancer_arn = aws_lb.main.arn
  port              = each.value
  protocol          = "TCP"

  default_action {
    target_group_arn = aws_lb_target_group.main[each.value].arn
    type             = "forward"
  }
}

# The security group that allows backends to receive load balancer traffic.
#
# Note that due to use of aws_autoscaling_attachment in calling modules, the target groups for the load
# balancer operate in "instance" mode as that mode is required by aws_autoscaling_attachment.
#
# Previous notes (no longer applicable due to instance mode requirement):
#   Whitelist the lb private IPs.
#   Context: If registering targets by IP, the source IPs will be these lb private IPs.
#   However if registering targets by instance ID, the original source IPs are passed through,
#   and we'd need to allow ingress from every IP, which we'd rather not do.
#   So for now we only register targets by IP (target_type = "ip" in the aws_lb_target_group above).
#   If in the future we want the original source IPs, e.g., for logging, we can get them via the Proxy Protocol
#   (which haproxy speaks). See
#   https://docs.aws.amazon.com/elasticloadbalancing/latest/network/load-balancer-target-groups.html#proxy-protocol.
#   PS: Note that even when registering targets by instance ID, this ingress rule is required, for health checks.
resource "aws_security_group" "backend" {
  name        = "${var.name}-backend"
  description = "Allow all incoming traffic from load balancer to backends."
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = local.ports_set
    iterator = port
    content {
      from_port   = port.value
      to_port     = port.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"] # does not restrict to load balancer IPs due to seeing client source addresses
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.extra_tags
}

# Data source that fetches attributes of the toolchainlabs.com. hosted zone.
data "aws_route53_zone" "main" {
  name = var.domain
}

resource "aws_route53_record" "elb" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "${var.name}.${data.aws_route53_zone.main.name}"
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
output "target_group_arns" {
  value = [for port in keys(aws_lb_target_group.main) : aws_lb_target_group.main[port].arn]
}
