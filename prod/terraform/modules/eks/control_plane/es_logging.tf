# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  # namespace:serviceaccount
  # prod/helm/observability/logging/values.yaml
  fluentbit_service_account = "logging:fluentbit"
}

resource "aws_iam_role" "fluent_bit" {
  name = "k8s.${var.cluster_name}.fluent-bit.service"
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
              "${local.oidc_provider}:sub" : "system:serviceaccount:${local.fluentbit_service_account}"
            }
          }
        }
      ]
    }
  )
}