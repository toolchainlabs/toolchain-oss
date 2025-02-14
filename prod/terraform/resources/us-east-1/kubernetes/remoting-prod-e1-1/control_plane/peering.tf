# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# defines reosurces (security group) that will allow the prod cluster to access the remoting cluster via VPC peering

data "aws_vpc" "main" {
  tags = {
    Name = "main"
  }
}

data "aws_security_group" "prod_cluster_nodes" {
  vpc_id = data.aws_vpc.main.id
  name   = "k8s.prod-e1-1.nodes"
}

resource "aws_security_group" "peer_vpc_ingress_alb" {
  name        = "k8s.${local.cluster_name}.vpc-ingress"
  description = "cluster ${local.cluster_name} internal load balancers accessible via VPC endpoint from main VPC."
  vpc_id      = local.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [data.aws_security_group.prod_cluster_nodes.id]
    description     = "From k8s prod cluster nodes (for grafana) to ALB ingress on remoting prod cluster"
  }

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [data.aws_security_group.prod_cluster_nodes.id]
    description     = "From k8s prod cluster nodes (for grafana) to ALB ingress on remoting prod cluster"
  }
}

resource "aws_security_group_rule" "peer_vpc_ingress_to_nodes" {
  description              = "Allow remoting-prod-e1-1 cluster nodes to receive traffic from VPC Peer ingress ALBs."
  type                     = "ingress"
  source_security_group_id = aws_security_group.peer_vpc_ingress_alb.id
  security_group_id        = module.control_plane.nodes_security_group_id
  # Ingress(s) map to k8s endpoints which are on the pod ports so keeping this fully open for now.
  from_port = 0
  to_port   = 65535
  protocol  = "-1"
}