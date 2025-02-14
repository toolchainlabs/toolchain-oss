# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_iam_account_password_policy" "default" {
  minimum_password_length        = 25
  hard_expiry                    = false
  max_password_age               = 45
  allow_users_to_change_password = true
  password_reuse_prevention      = 16

  require_lowercase_characters = true
  require_numbers              = true
  require_uppercase_characters = true
  require_symbols              = true
}