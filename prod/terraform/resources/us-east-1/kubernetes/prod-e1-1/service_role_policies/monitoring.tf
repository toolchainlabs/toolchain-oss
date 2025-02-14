# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_iam_policy" "es_logging_readonly" {
  name = "elasticsearch.prod-logging.readonly"
}

resource "aws_iam_policy" "cloudwatch_monitoring_policy" {
  name        = "cloudwatch-monitoring"
  description = "Access to cloudwatch metrics for monitoring in k8s cluster"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect   = "Allow",
          Action   = ["cloudwatch:ListMetrics", "cloudwatch:GetMetricStatistics", "cloudwatch:GetMetricData"],
          Resource = "*"
        }
      ]
  })
}

resource "aws_iam_role" "monitoring_role" {
  # See monitoring/values.yaml (Monitoring helm chart)
  name = "k8s.${local.cluster}.monitoring.cloudwatch.service"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect    = "Allow"
          Principal = { Federated = local.oidc_provider_arn }
          Action    = "sts:AssumeRoleWithWebIdentity"
          Condition = {
            StringEquals = {
              "${local.oidc_provider}:sub" : "system:serviceaccount:monitoring:cloudwatch-exporter"
            }
        } }
      ]
    }
  )
}

resource "aws_iam_role" "grafana_role" {
  name = "k8s.${local.cluster}.monitoring.grafana.service"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Effect    = "Allow",
          Principal = { Federated = local.oidc_provider_arn }
          Action    = "sts:AssumeRoleWithWebIdentity"
          Condition = {
            StringEquals = {
              "${local.oidc_provider}:sub" : "system:serviceaccount:monitoring:grafana"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "monitoring_role_policies" {
  role       = aws_iam_role.monitoring_role.name
  policy_arn = aws_iam_policy.cloudwatch_monitoring_policy.arn
}

resource "aws_iam_role_policy_attachment" "grafana_cw_role_policies" {
  role       = aws_iam_role.grafana_role.name
  policy_arn = aws_iam_policy.cloudwatch_monitoring_policy.arn
}

resource "aws_iam_role_policy_attachment" "grafana_es_role_policies" {
  role       = aws_iam_role.grafana_role.name
  policy_arn = data.aws_iam_policy.es_logging_readonly.arn
}
