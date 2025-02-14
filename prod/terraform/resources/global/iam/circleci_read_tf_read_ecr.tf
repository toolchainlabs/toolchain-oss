# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services#configuring-the-role-and-trust-policy

locals {
  ecr_repo_arn_base       = "arn:aws:ecr:us-east-1:${local.account_id}:repository"
  circle_ci_oidc_provider = "oidc.circleci.com/org/${local.toolchain_org_id_in_circleci}"
}
resource "aws_iam_role" "circleci_role" {
  # https://circleci.com/docs/openid-connect-tokens/#setting-up-aws
  name        = "circleci-jobs-role"
  description = "Allow Github actions to assume a role for the Toolchain repo."
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Principal = { Federated = "arn:aws:iam::${local.account_id}:oidc-provider/${local.circle_ci_oidc_provider}" },
          Effect    = "Allow",
          Action    = "sts:AssumeRoleWithWebIdentity",
          Condition = { StringEquals = { "${local.circle_ci_oidc_provider}:aud" = [local.toolchain_org_id_in_circleci] } }
        }
      ]
    }
  )
}

resource "aws_iam_policy" "read_ecr_images" {
  name = "read-ci-ecr-images"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow",
          Action = [
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage",
            "ecr:DescribeImages",
            "ecr:DescribeRepositories",
            "ecr:ListImages",
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetRepositoryPolicy"
          ],
          Resource = ["${local.ecr_repo_arn_base}/ci", "${local.ecr_repo_arn_base}/ci-devops"],
        },
        {
          Effect   = "Allow",
          Action   = "ecr:GetAuthorizationToken",
          Resource = "*"
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "circleci_read_tf" {
  role       = aws_iam_role.circleci_role.name
  policy_arn = data.aws_iam_policy.terraform_read_only.arn
}

resource "aws_iam_role_policy_attachment" "circleci_read_ecr" {
  role       = aws_iam_role.circleci_role.name
  policy_arn = aws_iam_policy.read_ecr_images.arn
}