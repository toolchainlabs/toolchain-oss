# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for dynamodb table access policies.

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}


locals {
  region     = data.aws_region.current.name
  account_id = data.aws_caller_identity.current.account_id
  table_arn  = "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.table_name}"
}


resource "aws_iam_policy" "dynamodb_access_policy" {
  name        = "${var.table_name}-readwrite"
  description = "Access dynamodb table ${var.table_name}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "dynamodb:BatchGetItem",
            "dynamodb:BatchWriteItem",
            "dynamodb:PutItem",
            "dynamodb:GetItem",
            "dynamodb:Query",
            "dynamodb:DeleteItem",
            "dynamodb:UpdateItem"
          ],
          Resource = ["${local.table_arn}", "${local.table_arn}/index/*"]
        }
      ]
    }
  )
}


output "policy_name" {
  value = aws_iam_policy.dynamodb_access_policy.name
}