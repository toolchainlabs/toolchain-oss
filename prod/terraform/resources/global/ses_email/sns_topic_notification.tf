# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# See: https://docs.aws.amazon.com/ses/latest/dg/configure-sns-notifications.html

resource "aws_sns_topic" "email_delivery" {
  name = "ses-delivery"
  tags = {
    toolchain_cost_center = "webapp"
  }
}

resource "aws_ses_identity_notification_topic" "bounce" {
  topic_arn                = aws_sns_topic.email_delivery.arn
  notification_type        = "Bounce"
  identity                 = aws_ses_domain_identity.toolchain_com.domain
  include_original_headers = true
}

resource "aws_ses_identity_notification_topic" "complaint" {
  topic_arn                = aws_sns_topic.email_delivery.arn
  notification_type        = "Complaint"
  identity                 = aws_ses_domain_identity.toolchain_com.domain
  include_original_headers = true
}

resource "aws_ses_identity_notification_topic" "delivery" {
  topic_arn                = aws_sns_topic.email_delivery.arn
  notification_type        = "Delivery"
  identity                 = aws_ses_domain_identity.toolchain_com.domain
  include_original_headers = true
}
