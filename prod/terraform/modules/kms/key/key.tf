# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for a KMS encryption key.


# The key.
resource "aws_kms_key" "main" {
}

# The human-friendly alias of the key.
resource "aws_kms_alias" "main" {
  name          = "alias/${var.alias}"
  target_key_id = aws_kms_key.main.key_id
}

# The key's id.
output "key_id" {
  value = aws_kms_key.main.key_id
}

# The key's ARN.
output "arn" {
  value = aws_kms_key.main.arn
}