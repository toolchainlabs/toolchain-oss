# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  now_timestamp = formatdate("YYYYMMDDHHmm", timestamp())
  ami_name = "ubuntu-eks-node-v${var.kubernetes_version_minor}-${local.now_timestamp}"
}

source "amazon-ebs" "ubuntu2004" {
  ami_name = local.ami_name
  ami_description = "EKS Node AMI with Ubuntu 20.04 LTS"
  ami_regions = ["us-east-1"]
  ami_virtualization_type = "hvm"
  # Authorize our AWS Account ID to access this AMI. By default, only the user creating the AMI may access it.
  ami_users = ["283194185447"]

  tags = {
    "Name" = local.ami_name
    "kubernetes" = "${local.kubernetes_version}/${local.kubernetes_build_date}/bin/linux/x86_64"
  }

  # Build the AMI in this region on a m4.large instance.
  region = "us-east-1"
  instance_type = "m4.large"
  associate_public_ip_address = true

  launch_block_device_mappings {
    device_name = "/dev/xvda"
    volume_type = "gp2"
    volume_size = "4"
    delete_on_termination = true
  }

  ami_block_device_mappings {
    device_name = "/dev/xvda"
    volume_type = "gp2"
    volume_size = var.worker_disk_size
    delete_on_termination = true
  }

  # Select the base AMI to use to build this AMI
  # Ubuntu 20.04 LTS from Canonical
  source_ami_filter {
    filters = {
      name = "ubuntu/images/*ubuntu*20.04-amd64-server-*"
      virtualization-type = "hvm"
      root-device-type = "ebs"
    }

    owners = ["099720109477"] # Canonical
    most_recent = true
  }

  # Select the public subnet on the VPC "main".
  vpc_filter {
    filter {
      name = "tag:Name"
      value = "main"
    }
  }
  subnet_filter {
    filter {
      name = "tag:Name"
      value = "public"
    }
  }

  # Use SSH to the `ubuntu` user to provision the instance.
  communicator = "ssh"
  ssh_username = "ubuntu"
}
