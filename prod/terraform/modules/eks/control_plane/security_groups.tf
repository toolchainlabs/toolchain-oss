# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_security_group" "control_plane" {
  name        = "k8s.${var.cluster_name}.control-plane"
  description = "The ${var.cluster_name} EKS cluster control plane."
  vpc_id      = var.vpc_id

  # This security group's ingress rules are not inlined, since they can be added to elsewhere (e.g., in node config).
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = var.extra_tags
}

# See https://learn.hashicorp.com/terraform/aws/eks-intro and
# https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html.

resource "aws_security_group" "nodes" {
  name        = "k8s.${var.cluster_name}.nodes"
  description = "Nodes in the ${var.cluster_name} EKS cluster."
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.extra_tags, {
    "Name"                                      = "${var.cluster_name}-nodes"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  })
}

resource "aws_security_group" "external_load_balancers" {
  name        = "k8s.${var.cluster_name}.ingress"
  description = "cluster ${var.cluster_name} external load balancers."
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
  tags = merge(var.extra_tags, {
    scheme = "internet-facing"
  })
}

resource "aws_security_group" "external_load_balancers_vpn" {
  count       = var.has_ingress && var.vpn_ingress_secrity_group_id != "" ? 1 : 0
  name        = "k8s.${var.cluster_name}.vpn.ingress"
  description = "cluster ${var.cluster_name} external load balancers accessible via vpn."
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [var.vpn_ingress_secrity_group_id]

  }

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [var.vpn_ingress_secrity_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.extra_tags
}

resource "aws_security_group_rule" "nodes_to_control_plane" {
  description              = "Allow ${var.cluster_name} nodes to communicate with the control plane."
  type                     = "ingress"
  source_security_group_id = aws_security_group.nodes.id
  security_group_id        = aws_security_group.control_plane.id
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "control_plane_to_nodes" {
  description              = "Allow the ${var.cluster_name} control plane to communicate with kubelets and pods."
  type                     = "ingress"
  source_security_group_id = aws_security_group.control_plane.id
  security_group_id        = aws_security_group.nodes.id
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "node_to_node" {
  description              = "Allow nodes in the ${var.cluster_name} cluster to communicate with each other."
  type                     = "ingress"
  source_security_group_id = aws_security_group.nodes.id
  security_group_id        = aws_security_group.nodes.id
  from_port                = 0
  to_port                  = 65535
  protocol                 = "-1"
}

resource "aws_security_group_rule" "external_lbs_to_nodes" {
  description              = "Allow ${var.cluster_name} nodes to receive traffic from external load balancers."
  type                     = "ingress"
  source_security_group_id = aws_security_group.external_load_balancers.id
  security_group_id        = aws_security_group.nodes.id
  from_port                = 0
  to_port                  = 65535
  protocol                 = "-1"
}

resource "aws_security_group_rule" "internal_lbs_to_nodes" {
  count                    = var.has_ingress && var.vpn_ingress_secrity_group_id != "" ? 1 : 0
  description              = "Allow ${var.cluster_name} nodes to receive traffic from internal (vpn) load balancers."
  type                     = "ingress"
  source_security_group_id = aws_security_group.external_load_balancers_vpn[0].id
  security_group_id        = aws_security_group.nodes.id
  # Will lock this down to port 80 if this works.
  from_port = 0
  to_port   = 65535
  protocol  = "-1"
}

output "nodes_security_group_id" {
  value = aws_security_group.nodes.id
}
