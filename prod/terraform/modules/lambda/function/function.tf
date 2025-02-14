# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_security_group" "vpc_security_group" {
  vpc_id = var.vpc_id
  name   = var.security_group_name
}


# Data source for fetching attributes of the VPC's local route table.
data "aws_route_table" "local" {
  vpc_id = var.vpc_id
  tags = {
    "Name" = "local"
  }
}

locals {
  tags = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
}

module "lambda_subnets" {
  source               = "../../vpc/subnets"
  vpc_id               = var.vpc_id
  first_netnum         = var.first_netnum
  cardinality          = 1
  name                 = "${var.function_name}-lambda"
  local_route_table_id = data.aws_route_table.local.id
}


resource "aws_iam_role" "lambda" {
  name = var.function_name
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Action = "sts:AssumeRole",
          Principal = {
            Service = "lambda.amazonaws.com"
          },
          Effect = "Allow"
        }
      ]
    }
  )
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.function_name}-base"
  description = "Base policy for ${var.function_name} lambda"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Action = [
            "ec2:CreateNetworkInterface",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DeleteNetworkInterface"

          ],
          Resource = "*",
          Effect   = "Allow"
        },
        {
          Action = [
            "logs:CreateLogStream",
            "logs:CreateLogGroup",
            "logs:PutLogEvents"
          ],
          Resource = "arn:aws:logs:*:*:*",
          Effect   = "Allow"
        }
      ]
    }
  )
}

locals {
  policy_arns = concat([aws_iam_policy.lambda_policy.arn], var.extra_policies_arns)
}

resource "aws_iam_role_policy_attachment" "lambda_role_policies" {
  count = length(local.policy_arns)

  role       = aws_iam_role.lambda.name
  policy_arn = element(local.policy_arns, count.index)
}

resource "aws_lambda_function" "function" {
  function_name = var.function_name
  role          = aws_iam_role.lambda.arn
  handler       = "lambdex_handler.handler"
  runtime       = "python3.9"
  memory_size   = 192
  timeout       = var.timeout
  s3_bucket     = "artifacts.us-east-1.toolchain.com"
  s3_key        = var.s3_key
  tags          = local.tags
  vpc_config {
    subnet_ids         = module.lambda_subnets.ids
    security_group_ids = [data.aws_security_group.vpc_security_group.id]
  }
  environment {
    variables = var.environment_variables
  }
}

output "function_arn" {
  value = aws_lambda_function.function.arn
}