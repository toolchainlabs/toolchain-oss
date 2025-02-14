# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  # namespace:serviceaccount
  # prod/helm/devops/aws-cost-reporter/templates/cost-reporter-job.yaml
  aws_cost_reporter_service_account = "devops:aws-cost-reporter"
}
resource "aws_iam_policy" "cost_reporter_policy" {
  name        = "cost_explorer_reporter_policy"
  description = "Policy used by AWS Cost reporter job."
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {

          Effect = "Allow",
          Action = [
            "ce:GetCostAndUsage"
          ],
          Resource = "*"
        }
      ]
    }
  )
}

resource "aws_iam_role" "aws_cost_reporter" {
  name = "k8s.${local.cluster}.aws-cost-reporter.job"
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
              "${local.oidc_provider}:sub" : "system:serviceaccount:${local.aws_cost_reporter_service_account}"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "aws_cost_reporter_policies" {
  role       = aws_iam_role.aws_cost_reporter.name
  policy_arn = aws_iam_policy.cost_reporter_policy.arn
}
