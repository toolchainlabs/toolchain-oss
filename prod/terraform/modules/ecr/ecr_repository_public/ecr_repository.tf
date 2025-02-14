# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for an ECR public image repository.

resource "aws_ecrpublic_repository" "main" {
  repository_name = var.name
}