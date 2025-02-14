# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  ami_id          = "ami-0b003f49defef9910"
  data_device     = "/dev/sdg"
  metadata_device = "/dev/sdh"
}

data "aws_subnet" "private" {
  vpc_id            = var.vpc_id
  availability_zone = var.availability_zone
  filter {
    name   = "tag:Name"
    values = ["private"]
  }
}
data "aws_security_group" "from_bastion" {
  vpc_id = var.vpc_id
  name   = "from_bastion"
}


data "cloudinit_config" "config" {
  part {
    filename     = "cas-cloud-init.cfg"
    content_type = "text/cloud-config"
    content = templatefile("${path.module}/cas-cloud-init.yaml", {
      data_ebs_block_device     = local.data_device
      metadata_ebs_block_device = "/dev/sdh"
    })
  }
}

resource "aws_instance" "cas" {
  ami           = local.ami_id
  instance_type = "m5.large"

  availability_zone = var.availability_zone

  user_data_base64 = data.cloudinit_config.config.rendered

  iam_instance_profile = "cas"

  subnet_id = data.aws_subnet.private.id
  security_groups = [
    data.aws_security_group.from_bastion.id,
  ]

  root_block_device {
    volume_type           = "gp2"
    volume_size           = 20
    delete_on_termination = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_volume_attachment" "data" {
  device_name = local.data_device
  volume_id   = var.cas_volume_id
  instance_id = aws_instance.cas.id
}

resource "aws_volume_attachment" "metadata" {
  device_name = local.metadata_device
  volume_id   = var.metadata_volume_id
  instance_id = aws_instance.cas.id
}
