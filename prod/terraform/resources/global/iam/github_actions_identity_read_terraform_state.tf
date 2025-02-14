# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services#configuring-the-role-and-trust-policy
resource "aws_iam_role" "gha_assume_role_for_terraform_provider_upgrade" {
  name = "github-actions-tf-provider-upgrade"
  # see: https://github.com/toolchainlabs/toolchain/blob/master/.github/workflows/terraform-providers-upgrade.yml
  description = "Allow Github actions to read terraform state in order to run the terraform provider upgrade workflow."

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
            StringEquals = {
              "token.actions.githubusercontent.com:sub" = [
                "repo:toolchainlabs/toolchain:ref:refs/heads/master"
              ],
              "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
            }
          }
        }
  ] })
}


resource "aws_iam_role_policy_attachment" "gha_role_terraform_provider_upgrade" {
  role       = aws_iam_role.gha_assume_role_for_terraform_provider_upgrade.name
  policy_arn = data.aws_iam_policy.terraform_read_only.arn
}