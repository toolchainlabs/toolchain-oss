# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

module "devbox_instance_profile" {
  source     = "../../modules/ec2/instance_profile"
  name       = "devbox"
  ssh_access = true
}

# Allow the devbox access to ECR repositories.
resource "aws_iam_role_policy_attachment" "ecr_repository_access" {
  role       = module.devbox_instance_profile.role_name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
}

