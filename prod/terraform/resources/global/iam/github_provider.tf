# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html#idp_oidc_Create_GitHub

resource "aws_iam_openid_connect_provider" "github" {
  # https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services#adding-the-identity-provider-to-aws
  url = "https://token.actions.githubusercontent.com"

  # AKA audiences
  client_id_list = ["sts.amazonaws.com"]
  # https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc_verify-thumbprint.html
  # Also using the AWS IAM console. https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/identity_providers/create
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}
