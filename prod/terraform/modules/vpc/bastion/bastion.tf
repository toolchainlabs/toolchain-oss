# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for a bastion host.
# Data source that fetches attributes of available AZs.
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_vpc" "vpc" {
  tags = {
    Name = var.vpc_name
  }
}

locals {
  bastion_name = join(".", compact(["bastion", var.env_name, element(data.aws_availability_zones.available.names, var.availability_zone_index)]))
}

# Data source for fetching attributes of the VPC's public route table.
data "aws_route_table" "public" {
  vpc_id = data.aws_vpc.vpc.id
  tags = {
    "Name" = "public"
  }
}

# The subnet for the bastion host.
module "bastion_subnet" {
  source                = "../subnet"
  vpc_id                = data.aws_vpc.vpc.id
  name                  = local.bastion_name
  availability_zone     = element(data.aws_availability_zones.available.names, var.availability_zone_index)
  netnum                = 202 + var.availability_zone_index
  public_route_table_id = data.aws_route_table.public.id
}
module "amis" {
  source = "../../ec2/amis"
}

# Data source that fetches attributes of the bastion security group.
data "aws_security_group" "bastion" {
  vpc_id = data.aws_vpc.vpc.id
  name   = "bastion-${var.vpc_name}"
}

# The userdata base script.
module "userdata_base" {
  source = "../../ec2/userdata/base"
}

# The bastion host itself.
resource "aws_instance" "bastion_host" {
  ami           = module.amis.amazon_linux_2_ami
  instance_type = "t2.micro"
  subnet_id     = module.bastion_subnet.id
  vpc_security_group_ids = concat([
    data.aws_security_group.bastion.id,
  ], var.extra_security_groups)
  associate_public_ip_address = true
  iam_instance_profile        = "bastion"
  key_name                    = var.key_pair
  # The user data script that will be run on the instance at startup to initialize the devbox.
  user_data = templatefile("${path.module}/bastion_user_data.sh", {
    __TF_userdata_base = module.userdata_base.script
  })

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.extra_tags, {
    Name = local.bastion_name
  })
}

# Data source that fetches attributes of the toolchain.private. hosted zone.
data "aws_route53_zone" "toolchain_private" {
  name         = "toolchain.private."
  private_zone = true
}

resource "aws_route53_record" "bastion_private" {
  zone_id = data.aws_route53_zone.toolchain_private.zone_id
  name    = "${local.bastion_name}.${data.aws_route53_zone.toolchain_private.name}"
  type    = "A"
  ttl     = "300"
  records = [aws_instance.bastion_host.private_ip]
}

# The public dns name of the bastion host.
output "private_dns_name" {
  value = aws_route53_record.bastion_private.name
}

# The public IP address of the bastion host.
output "public_ip" {
  value = aws_instance.bastion_host.public_ip
}
