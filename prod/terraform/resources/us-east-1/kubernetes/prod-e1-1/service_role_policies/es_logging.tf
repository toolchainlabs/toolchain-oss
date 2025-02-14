# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  # namespace:serviceaccount
  # prod/helm/observability/logging/templates/es-curator-job.yaml
  curator_service_account = "logging:curator"
}

resource "aws_iam_role" "es_logging_curator" {
  name = "k8s.${local.cluster}.es-logging-curator.job"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Effect    = "Allow"
          Principal = { Federated = local.oidc_provider_arn }
          Action    = "sts:AssumeRoleWithWebIdentity"
          Condition = {
            StringEquals = {
              "${local.oidc_provider}:sub" : "system:serviceaccount:${local.curator_service_account}"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "es_logging_curator_policies" {
  role       = aws_iam_role.es_logging_curator.name
  policy_arn = "arn:aws:iam::${local.account_id}:policy/elasticsearch.${local.logging_es_domain_name}.readwrite"
}