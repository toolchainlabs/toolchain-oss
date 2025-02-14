# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for an ECR image repository.

resource "aws_ecr_repository" "main" {
  name = var.name
}

# Note that ECR only partially supports resource-level permissions, so it's not helpful to create
# repository-specific readonly/readwrite policies here. Instead we can just use the managed policies,
# which apply to all ECR repositories.
# See https://docs.aws.amazon.com/AmazonECR/latest/userguide/ecr_managed_policies.html.
