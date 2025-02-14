# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  binaries_bucket = "binaries.toolchain.com"
}

# https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services#configuring-the-role-and-trust-policy
resource "aws_iam_role" "gha_assume_role_for_publish_binaries" {
  name        = "github-actions-for-toolchain-repo"
  description = "Allow Github actions to assume a role for the Toolchain repo."
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",

      Statement = [
        { Principal = {
          Federated = "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
          }
          Effect = "Allow",
          Action = "sts:AssumeRoleWithWebIdentity",
          Condition = {
            # https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect#configuring-the-subject-in-your-cloud-provider
            StringLike = {
              "token.actions.githubusercontent.com:sub" = [
                "repo:toolchainlabs/toolchain:ref:refs/heads/master",
                "repo:toolchainlabs/toolchain:ref:refs/tags/remote-exec-worker-v*",
              ],
              "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
            }
          }
        }
  ] })
}

resource "aws_iam_policy" "publish_binaries" {
  # https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push.html#image-push-iam
  name = "publish_binaries"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "s3:ListBucket",
            "s3:GetBucketAcl"
          ]
          Resource = "arn:aws:s3:::${local.binaries_bucket}"
        },
        {
          Effect = "Allow",
          Action = [
            "s3:PutObject",
            "s3:PutObjectAcl",
            "s3:GetObject",
            "s3:CreateMultipartUpload"
          ],
          Resource = "arn:aws:s3:::${local.binaries_bucket}/*"
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "gha_role_publish_binaries" {
  role       = aws_iam_role.gha_assume_role_for_publish_binaries.name
  policy_arn = aws_iam_policy.publish_binaries.arn
}