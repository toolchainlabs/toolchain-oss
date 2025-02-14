# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_iam_policy" "send_email" {
  name        = "send-email"
  description = "Allow sending email."
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "ses:SendEmail",
            "ses:SendRawEmail"
          ],
          Resource = ["*"]
        }
      ]
    }
  )
}

output "send_email_arn" {
  value = aws_iam_policy.send_email.arn
}

