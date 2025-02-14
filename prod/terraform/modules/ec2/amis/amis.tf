# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Data sources for fetching the per-region ids of the specific AMI versions we use.

data "aws_ami" "amazon_linux_2" {
  owners = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-2.0.20220805.0-x86_64-ebs"]
  }
}


data "aws_caller_identity" "current" {}

data "aws_ami" "devbox" {
  most_recent = true
  owners      = [data.aws_caller_identity.current.account_id]
  filter {
    name   = "tag:Name"
    values = ["devbox"]
  }
}

output "amazon_linux_2_ami" {
  value = data.aws_ami.amazon_linux_2.id
}

output "devbox_ami" {
  value = data.aws_ami.devbox.id
}
