# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# https://circleci.com/blog/openid-connect-identity-tokens/
# https://circleci.com/docs/openid-connect-tokens/

locals {
  # https://app.circleci.com/settings/organization/github/toolchainlabs/overview
  toolchain_org_id_in_circleci = "19d29aef-2e15-4e63-b3f1-06779bb0d5fe"
}

resource "aws_iam_openid_connect_provider" "circleci" {

  # https://circleci.com/docs/openid-connect-tokens/#setting-up-aws
  url = "https://oidc.circleci.com/org/${local.toolchain_org_id_in_circleci}"
  # AKA audiences
  client_id_list  = [local.toolchain_org_id_in_circleci]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
}
