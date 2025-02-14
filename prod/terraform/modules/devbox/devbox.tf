# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resource for a machine devs can SSH into and perform resource-intensive tasks on, such as docker image builds.


# Data source to read attributes of the general-use private network.
data "aws_subnet" "private" {
  vpc_id = var.vpc_id
  filter {
    name   = "tag:Name"
    values = ["private"]
  }
}

# Data source that fetches attributes of the security group that allows
# incoming SSH connections from the bastion.
data "aws_security_group" "from_bastion" {
  vpc_id = var.vpc_id
  name   = "from_bastion"
}

locals {
  volume = "/dev/sdg"
  name   = replace(var.name, "_", "-")
}

# Access to AMI ids.
module "ec2" {
  source = "../ec2/amis"
}

data "aws_security_group" "can_access_all_dbs" {
  vpc_id = var.vpc_id
  tags = {
    "toolchain.com/sg/can-access-all-dbs" = "1"
  }
}

locals {
  security_groups = [
    data.aws_security_group.from_bastion.id,
    data.aws_security_group.can_access_all_dbs.id,
  ]
}

data "cloudinit_config" "config" {
  part {
    filename     = "disk_init.cfg"
    content_type = "text/cloud-config"
    content = templatefile("${path.module}/disk-cloud-init.yaml", {
      disk_device = local.volume
    })
  }
}

resource "aws_instance" "devbox" {
  ami           = var.ami_override != "" ? var.ami_override : module.ec2.devbox_ami
  instance_type = var.instance_type
  # The devbox needs internet access.
  subnet_id                   = data.aws_subnet.private.id
  vpc_security_group_ids      = local.security_groups
  associate_public_ip_address = false
  iam_instance_profile        = "devbox"
  key_name                    = var.key_pair
  disable_api_termination     = true

  root_block_device {
    volume_type           = "gp2"
    volume_size           = 128 # 128gb
    delete_on_termination = true
    iops                  = 384
    tags = {
      Name = "devbox-root"
    }
  }

  user_data_base64 = data.cloudinit_config.config.rendered

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = local.name
  }
}

resource "aws_volume_attachment" "data" {
  device_name = local.volume
  volume_id   = var.data_volume_id
  instance_id = aws_instance.devbox.id
}

# Data source that fetches attributes of the toolchain.private. hosted zone.
data "aws_route53_zone" "toolchain_private" {
  name         = "toolchain.private."
  private_zone = true
}

locals {
  private_dns_name = "${local.name}.${data.aws_route53_zone.toolchain_private.name}"
}

resource "aws_route53_record" "dns" {
  zone_id = data.aws_route53_zone.toolchain_private.zone_id
  name    = local.private_dns_name
  type    = "A"
  ttl     = "300"
  records = [aws_instance.devbox.private_ip]
}

# The private IP address of the devbox.
output "private_dns_name" {
  value = local.private_dns_name
}

# The private IP address of the devbox.
output "private_ip" {
  value = aws_instance.devbox.private_ip
}
