# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "cloudwatch-logs"
  description = "Allow instance to interact with cloudwatch logs agent."
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents",
            "logs:DescribeLogStreams"
          ],
          Resource = [
            "arn:aws:logs:*:*:*"
          ]
        }
      ]
    }
  )

}

output "cloudwatch_logs_policy_arn" {
  value = aws_iam_policy.cloudwatch_logs.arn
}

