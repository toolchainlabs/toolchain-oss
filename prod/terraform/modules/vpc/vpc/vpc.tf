# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for a VPC.

# Data source to fetch the name of the AWS region we're operating in.
data "aws_region" "current" {}

locals {
  region = data.aws_region.current.name
}

# Data source to read remote state about global resources.
data "terraform_remote_state" "global" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/global"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

# Data source that fetches attributes of available AZs.
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  netnum = coalesce(var.netnum, lookup(var.region_numbers, local.region))
}

resource "aws_vpc" "vpc" {
  cidr_block           = cidrsubnet(var.base_cidr_block, 4, local.netnum)
  enable_dns_hostnames = true
  tags = merge(var.vpc_tags, {
    Name = var.name
  })
}

# A general-use public subnet.
# Note that we don't call the subnet module here, because that requires the
# NAT route table to exist, and we require this subnet in order to create the NAT gateway.
resource "aws_subnet" "public" {
  cidr_block        = cidrsubnet(aws_vpc.vpc.cidr_block, 8, 200)
  vpc_id            = aws_vpc.vpc.id
  availability_zone = element(data.aws_availability_zones.available.names, var.availability_zone_index)
  tags = {
    Name = "public"
  }
}

# The Internet gateway.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "main"
  }
}

# The NAT gateway.
resource "aws_eip" "nat" {
  vpc = true
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id
  tags = {
    Name = "main"
  }
}

# The public route table.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "public"
  }
}

resource "aws_route" "public" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

# The private route table.
resource "aws_route_table" "nat" {
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "nat"
  }
}

resource "aws_route" "nat" {
  route_table_id         = aws_route_table.nat.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main.id
}

# The local route table.
resource "aws_route_table" "local" {
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "local"
  }
}

# A general-use private subnet.
# Useful, e.g., for Lambda functions that require internet access (e.g., to access AWS services
# that don't have VPC endpoints). Lambdas are not assigned public IPs, so they can only access
# the internet via a NAT gateway.
module "private_subnet" {
  source             = "../subnet"
  vpc_id             = aws_vpc.vpc.id
  name               = "private"
  availability_zone  = element(data.aws_availability_zones.available.names, var.availability_zone_index)
  netnum             = "201"
  nat_route_table_id = aws_route_table.nat.id
}

# Public routing for the public subnet.
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# An S3 VPC endpoint.
resource "aws_vpc_endpoint" "s3" {
  vpc_id          = aws_vpc.vpc.id
  service_name    = "com.amazonaws.${local.region}.s3"
  route_table_ids = [aws_route_table.public.id, aws_route_table.nat.id, aws_route_table.local.id]
}

# A DynamoDB VPC endpoint.
resource "aws_vpc_endpoint" "dynamodb" {
  count           = var.enable_dynamodb_route ? 1 : 0
  vpc_id          = aws_vpc.vpc.id
  service_name    = "com.amazonaws.${local.region}.dynamodb"
  route_table_ids = [aws_route_table.public.id, aws_route_table.nat.id, aws_route_table.local.id]
}

resource "aws_security_group" "can_access_all_dbs" {
  name        = "can-access-all-dbs-${var.name}"
  description = "For hosts allowed to connect to all dbs in the region."
  vpc_id      = aws_vpc.vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    "toolchain.com/sg/can-access-all-dbs" = "1"
  }
}

# The id of the VPC.
output "id" {
  value = aws_vpc.vpc.id
}

# The id of the public route table.
output "public_route_table" {
  value = aws_route_table.public.id
}

# The id of the private route table.
output "nat_route_table" {
  value = aws_route_table.nat.id
}

# The full network CIDR block for the VPC
output "cidr_block" {
  value = aws_vpc.vpc.cidr_block
}
