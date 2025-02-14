# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  # namespace:serviceaccount
  # prod/helm/devops/iam-keys-watcher/templates/iam-watcher-job.yaml
  iam_keys_watcher_service_account = "devops:iam-keys-watcher"
}
resource "aws_iam_policy" "iam_keys_watcher_policy" {
  name        = "iam_keys_watcher"
  description = "Policy used by iam_keys_watcher to monitor IAM Access keys and email users when they expire"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "ses:SendEmail",
            "iam:DeleteAccessKey",
            "iam:ListUsers",
            "iam:ListUserTags",
            "iam:ListAccessKeys"
          ],
          Resource = "*"
        }
      ]
    }
  )
}
resource "aws_iam_role" "iam_keys_watcher" {
  name = "k8s.${local.cluster}.iam-keys-watcher.job"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Principal = {
            Federated = local.oidc_provider_arn
          },
          Action = "sts:AssumeRoleWithWebIdentity",
          Condition = {
            StringEquals = {
              "${local.oidc_provider}:sub" : "system:serviceaccount:${local.iam_keys_watcher_service_account}"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "iam_keys_watcher_policies" {
  role       = aws_iam_role.iam_keys_watcher.name
  policy_arn = aws_iam_policy.iam_keys_watcher_policy.arn
}
