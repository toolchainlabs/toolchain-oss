# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

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

resource "aws_iam_role" "role" {
  name                  = var.name
  force_detach_policies = false
  tags                  = var.extra_tags
  description           = var.ssh_access ? "keymaker_require_iam_group=prod_ssh_users keymaker_linux_group_prefix=linux_" : var.name
  managed_policy_arns = concat(
    var.managed_policy_arns,
    # Allow the logs agent to ship logs to cloudwatch.
    [data.terraform_remote_state.global.outputs.cloudwatch_logs_policy_arn],
  var.ssh_access ? [data.terraform_remote_state.global.outputs.read_ssh_public_keys_policy_arn] : [])
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "ec2.amazonaws.com"
        },
        Effect = "Allow"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "read_ssh_public_keys" {
  count      = var.ssh_access ? 1 : 0
  role       = aws_iam_role.role.name
  policy_arn = data.terraform_remote_state.global.outputs.read_ssh_public_keys_policy_arn
}

# Allow the logs agent to ship logs to cloudwatch.
resource "aws_iam_role_policy_attachment" "cloudwatch_logs_permissions" {
  role       = aws_iam_role.role.name
  policy_arn = data.terraform_remote_state.global.outputs.cloudwatch_logs_policy_arn
}


resource "aws_iam_instance_profile" "instance_profile" {
  name = var.name
  role = aws_iam_role.role.name
}

# The name of the instance profile.
# In practice this is the same as the passed-in name, but it's good hygiene to output it
# for calling code to use.
output "name" {
  value = aws_iam_instance_profile.instance_profile.name
}

# The name of the role attached to the instance profile.
# In practice this is the same as the passed-in name, but it's good hygiene to output it
# for calling code to use.
output "role_name" {
  value = aws_iam_role.role.name
}

# The ARN of the role attached to the instance profile.
output "role_arn" {
  value = aws_iam_role.role.arn
}
