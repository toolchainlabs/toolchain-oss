# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  # namespace:serviceaccount
  # prod/helm/observability/logging/templates/es-curator-job.yaml
  curator_service_account = "logging:curator"
  rw_policy_arn           = "arn:aws:iam::${local.account_id}:policy/elasticsearch.${local.es_domain_name}.readwrite"
}

resource "aws_iam_role" "opensearch_dev_proxy" {
  name = "k8s.${local.cluster}.opensearch-dev-proxy.service"
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
            StringLike = {
              # see: prod/helm/dev-support/opensearch-dev-proxy/templates/deployment.yaml
              # Using * for namespace so it works in every dev cluster ns (different engieers)
              "${local.oidc_provider}:sub" : "system:serviceaccount:*:opensearch-dev-proxy"
            }
          }
        }
      ]
    }
  )
}


resource "aws_iam_role_policy_attachment" "opensearch_dev_proxy_policies" {
  role       = aws_iam_role.opensearch_dev_proxy.name
  policy_arn = local.rw_policy_arn
}

resource "aws_iam_role" "es_logging_curator" {
  name = "k8s.${local.cluster}.es-logging-curator.job"
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
  policy_arn = local.rw_policy_arn
}
