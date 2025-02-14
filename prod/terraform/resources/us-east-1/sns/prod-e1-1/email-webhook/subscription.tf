# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

terraform {
  backend "s3" {
    bucket         = "terraform.toolchainlabs.com"
    key            = "state/us-east-1/sns/prod-e1-1/email-webhook"
    region         = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_sns_topic" "email" {
  # see: prod/terraform/resources/global/ses_email/sns_topic_notification.tf
  name = "ses-delivery"
}

resource "aws_sns_topic_subscription" "prod_sub" {
  topic_arn = data.aws_sns_topic.email.arn
  protocol  = "https"
  endpoint  = "https://webhooks.toolchain.com/aws/ses/"
}
