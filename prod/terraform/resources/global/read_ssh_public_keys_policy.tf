# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_iam_policy" "read_ssh_public_keys" {
  name        = "read-ssh-public-keys"
  description = "Allow instance to read SSH public keys from IAM."
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "iam:GetSSHPublicKey",
            "iam:ListSSHPublicKeys",
            "iam:GetUser",
            "iam:ListGroups",
            "iam:GetGroup",
            "iam:ListGroupsForUser",
            "iam:GetRole",
            "sts:GetCallerIdentity"
          ],
          Resource = [
            "*"
          ]
        }
  ] })

}

output "read_ssh_public_keys_policy_arn" {
  value = aws_iam_policy.read_ssh_public_keys.arn
}

