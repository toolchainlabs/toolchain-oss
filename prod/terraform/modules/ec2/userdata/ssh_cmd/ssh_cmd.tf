# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A sourceable bash snippet that supports executing commands on toolchainlabs EC2 instances
# provisioned with ec2/userdata/ssh_key_setup.
#
# Sourcing scripts should define:
# TARGET_HOST: the host to scp or ssh to.
# SSH_TEST: A command string to execute on the TARGET_HOST via ssh to confirm it is ready.
#
# The snippet defines two functions for sourcing scripts to use:
# scp_cmd <from> <to>
# ssh_cmd <args...>
#

data "terraform_remote_state" "bastion" {
  backend = "s3"
  config = {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/${var.aws_region}/bastion"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

# The rendered ssh snippet.
output "script" {
  value = templatefile("${path.module}/ssh_cmd.sh", {
    # Use the dns name, not the ip address, so that we pick up any host-related .ssh/config.
    bastion_host = data.terraform_remote_state.bastion.outputs.dns_name
    ssh_timeout  = var.ssh_timeout
    ssh_wait     = var.ssh_wait
  })
}
