# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Terraform configuration for this connecting the main VPC (where we have the prod and dev k8s cluster) to the remoting VPC (with the remoting-prod-e1-1 k8s cluster)

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/vpc-peering"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}

data "aws_vpc" "remoting_prod_e1" {
  tags = {
    "Name" = "remoting-prod-e1-1"
  }
}

data "aws_route_table" "remoting_private_subnets" {
  vpc_id = data.aws_vpc.remoting_prod_e1.id
  tags = {
    "Name" = "nat"
  }
}

data "aws_route_table" "main_private_subnets" {
  vpc_id = data.aws_vpc.main.id
  tags = {
    "Name" = "local"
  }
}

data "aws_security_group" "peer_vpc_ingress_alb" {
  name = "k8s.remoting-prod-e1-1.vpc-ingress"
}

data "aws_security_group" "prod_cluster_nodes" {
  name = "k8s.prod-e1-1.nodes"
}


data "aws_route_table" "main_nat" {
  vpc_id = data.aws_vpc.main.id
  tags = {
    Name = "nat"
  }
}
data "aws_route_table" "main_public" {
  vpc_id = data.aws_vpc.main.id
  tags = {
    Name = "public"
  }
}

data "aws_route_table" "remoting_public" {
  vpc_id = data.aws_vpc.remoting_prod_e1.id
  tags = {
    Name = "public"
  }
}

resource "aws_vpc_peering_connection" "peer_with_remoting_e1_vpc" {
  peer_owner_id = data.aws_caller_identity.current.account_id
  peer_vpc_id   = data.aws_vpc.remoting_prod_e1.id
  vpc_id        = data.aws_vpc.main.id
  auto_accept   = true
}

resource "aws_route" "to_main_via_peer" {
  route_table_id            = data.aws_route_table.remoting_private_subnets.id
  destination_cidr_block    = data.aws_vpc.main.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer_with_remoting_e1_vpc.id
}

resource "aws_route_table" "es_logging_peer_route" {
  vpc_id = data.aws_vpc.main.id
  tags = {
    Name    = "remoting-logging"
    Product = "remoting"
  }
  route {
    cidr_block                = data.aws_vpc.remoting_prod_e1.cidr_block
    vpc_peering_connection_id = aws_vpc_peering_connection.peer_with_remoting_e1_vpc.id
  }
}

resource "aws_security_group_rule" "access_remoteing_alb_from_prod_nodes" {
  security_group_id        = data.aws_security_group.peer_vpc_ingress_alb.id
  description              = "From k8s prod cluster nodes (for grafana) to ALB ingress on remoting prod cluster"
  type                     = "ingress"
  protocol                 = "tcp"
  from_port                = 80
  to_port                  = 80
  source_security_group_id = data.aws_security_group.prod_cluster_nodes.id
}

resource "aws_route" "main_nat_to_remoting" {
  route_table_id            = data.aws_route_table.main_nat.id
  destination_cidr_block    = data.aws_vpc.remoting_prod_e1.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer_with_remoting_e1_vpc.id
}

resource "aws_route" "remoting_public_to_main" {
  route_table_id            = data.aws_route_table.remoting_public.id
  destination_cidr_block    = data.aws_vpc.main.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer_with_remoting_e1_vpc.id
}

resource "aws_route" "main_public_to_remoting" {
  # For VPN. allow VPN traffic from main VPC to be routed to the remoting VPC
  route_table_id            = data.aws_route_table.main_public.id
  destination_cidr_block    = data.aws_vpc.remoting_prod_e1.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer_with_remoting_e1_vpc.id
}