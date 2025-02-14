# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

module "bastion_instance_profile" {
  source     = "../../modules/ec2/instance_profile"
  name       = "bastion"
  ssh_access = true
}

resource "aws_iam_policy" "read_artifacts_from_s3" {
  name        = "read-artifacts-from-s3"
  description = "Allows the instance to read artifacts from the artifacts s3 bucket."
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect   = "Allow",
          Action   = ["s3:GetObject"],
          Resource = "arn:aws:s3:::artifacts.us-east-1.toolchain.com/prod/v1/bin/*"
        }
  ] })

}

resource "aws_iam_role_policy_attachment" "read_artifacts_from_s3" {
  role       = module.bastion_instance_profile.name
  policy_arn = aws_iam_policy.read_artifacts_from_s3.arn
}
