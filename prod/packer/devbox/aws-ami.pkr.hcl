# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Note:  The unreleased Packer 1.5.5 is required due to https://github.com/hashicorp/packer/issues/8684)
# for which the fix (https://github.com/hashicorp/packer/pull/8889) has landed but not been released.

source "amazon-ebs" "ubuntu1804" {
  ami_name = "devbox-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  ami_description = "Devbox image"
  ami_regions = ["us-east-1"]
  ami_virtualization_type = "hvm"
  # Authorize our AWS Account ID to access this AMI. By default, only the user creating the AMI may access it.
  ami_users = ["283194185447"]

  tag {
    key = "Name"
    value = "devbox"
  }

  # Build the AMI in this region on a t2.micro instance.
  region = "us-east-1"
  instance_type = "t2.micro"
  associate_public_ip_address = true

  # Select the base AMI to use to build this AMI
  # Ubuntu 18.04 LTS from Canonical
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
