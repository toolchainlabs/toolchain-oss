# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_iam_policy" "efs_dev_access" {
  name = "remote-cache-dev-file-system-access"
}

locals {
  # See: prod/helm/aws/aws-efs-csi-driver/templates/service-accont.yaml
  efs_csi_contrller_k8s_service_account = "kube-system:efs-csi-controller-sa" # namespace:serviceaccount
}

# see: https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html#efs-create-iam-resources
resource "aws_iam_role" "aws_efs_driver_role" {
  name = "k8s.${local.cluster}.aws-efs-csi-driver.driver"
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
              "${local.oidc_provider}:sub" : "system:serviceaccount:${local.efs_csi_contrller_k8s_service_account}"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "aws_efs_driver_policies" {
  role       = aws_iam_role.aws_efs_driver_role.name
  policy_arn = data.aws_iam_policy.efs_dev_access.arn
}
