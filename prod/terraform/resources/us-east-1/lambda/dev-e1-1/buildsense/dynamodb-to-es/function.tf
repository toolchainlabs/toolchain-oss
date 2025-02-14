# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/lambdas/dev-de-1/buildsense/dyanmodb-to-es"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}


data "aws_vpc" "main" {
  tags = {
    "Name" = "main"
  }
}
data "aws_region" "current" {}

data "aws_caller_identity" "current" {}
locals {
  account_id = data.aws_caller_identity.current.account_id
}
resource "aws_iam_policy" "dynamodb_streams" {
  name = "dev-buildsense-dynamodb-streams"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Action = [
            "dynamodb:GetShardIterator",
            "dynamodb:DescribeStream",
            "dynamodb:GetRecords",
            "dynamodb:ListStreams"
          ],
          Resource = "arn:aws:dynamodb:${data.aws_region.current.name}:${local.account_id}:table/dev-runinfo-v1/stream/*",
          Effect   = "Allow"
        }
      ]
    }
  )
}

locals {
  environment_variables = {
    "ES_HOST"     = "vpc-es-dev-1-rk4lyznh7j3ckq2gp7impmend4.us-east-1.es.amazonaws.com"
    "REGION_NAME" = "us-east-1"
    "SENTRY_DSN"  = "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709"
  }
}

data "aws_dynamodb_table" "dev_table" {
  name = "dev-runinfo-v1"
}

module "buildsense_dyanmodb_to_es" {
  source                = "../../../../../../modules/lambda/function"
  tag_cost_center       = "dev"
  function_name         = "dev-buildsense-dynamodb-to-es"
  first_netnum          = 65
  security_group_name   = "can-access-es-dev-1-es"
  environment_variables = local.environment_variables
  vpc_id                = data.aws_vpc.main.id
  extra_policies_arns   = [aws_iam_policy.dynamodb_streams.arn, "arn:aws:iam::${local.account_id}:policy/elasticsearch.es-dev-1.readwrite"]
  s3_key                = "dev/asher/bin/awslambda/dynamodb-to-es-lambda.zip"
}


resource "aws_lambda_event_source_mapping" "dynamodb_stream_source" {
  event_source_arn                   = data.aws_dynamodb_table.dev_table.stream_arn
  function_name                      = module.buildsense_dyanmodb_to_es.function_arn
  starting_position                  = "LATEST"
  maximum_batching_window_in_seconds = 3
}