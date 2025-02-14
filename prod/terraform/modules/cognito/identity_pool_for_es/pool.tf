# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_cognito_user_pools" "pools" {
  name = var.user_pool_name
}

locals {
  user_pool_id = tolist(data.aws_cognito_user_pools.pools.ids)[0]
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}


resource "aws_cognito_identity_pool" "identity_pool" {
  identity_pool_name = var.identity_pool_name
  cognito_identity_providers {
    client_id               = var.client_id
    provider_name           = "cognito-idp.${data.aws_region.current.name}.amazonaws.com/${local.user_pool_id}"
    server_side_token_check = true
  }
}

resource "aws_iam_role" "authenticated" {
  name = var.authenticated_role_name
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        },
        Action = "sts:AssumeRoleWithWebIdentity",
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.identity_pool.id
          },
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
    }
  )
}

resource "aws_iam_role_policy" "auth_policy" {
  name = "${var.authenticated_role_name}-es-full-access"
  role = aws_iam_role.authenticated.id
  policy = jsonencode({

    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "es:DescribeReservedElasticsearchInstanceOfferings",
          "es:DescribeReservedElasticsearchInstances",
          "es:ListDomainNames",
          "es:PurchaseReservedElasticsearchInstanceOffering",
          "es:DeleteElasticsearchServiceRole",
          "es:ListElasticsearchInstanceTypes",
          "es:DescribeElasticsearchInstanceTypeLimits",
          "es:ListElasticsearchVersions"
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = "es:*",
        Resource = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${var.es_domain_name}/*"
      }
    ]
    }
  )
}


data "aws_iam_role" "unauthenticated" {
  name = var.unauthenticated_role_name
}
resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.identity_pool.id
  roles = {
    "authenticated"   = aws_iam_role.authenticated.arn
    "unauthenticated" = data.aws_iam_role.unauthenticated.arn

  }
}

output "user_pool_id" {
  value = local.user_pool_id
}

output "identity_pool_id" {
  value = aws_cognito_identity_pool.identity_pool.id
}