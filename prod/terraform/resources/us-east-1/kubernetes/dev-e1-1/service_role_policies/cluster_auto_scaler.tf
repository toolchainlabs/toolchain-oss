# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# see: https://docs.aws.amazon.com/eks/latest/userguide/autoscaling.html#cluster-autoscaler

locals {
  # see: prod/helm/devops/cluster-autoscaler/values-dev.yaml
  cluster_autoscaler_k8s_service_account = "kube-system:dev-aws-cluster-autoscaler" # namespace:serviceaccount
}
resource "aws_iam_role" "aws_eks_cluster_auto_scaler" {
  name = "k8s.${local.cluster}.aws-eks-cluster-autoscaler"
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
              "${local.oidc_provider}:sub" : "system:serviceaccount:${local.cluster_autoscaler_k8s_service_account}"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_policy" "aws_eks_cluster_auto_scaler" {
  name        = "k8s.${local.cluster}.aws-eks-cluster-autoscalaer"
  description = "Autoscaler IAM policy for ${local.cluster}"
  policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [
        {
          Effect   = "Allow",
          Action   = ["autoscaling:SetDesiredCapacity", "autoscaling:TerminateInstanceInAutoScalingGroup"]
          Resource = "*"
          Condition = {
            StringEquals = {
              "aws:ResourceTag/k8s.io/cluster-autoscaler/${local.cluster}" : "owned"
            }
          }
        },
        {
          Effect = "Allow",
          Action = [
            "autoscaling:DescribeAutoScalingInstances",
            "autoscaling:DescribeAutoScalingGroups",
            "ec2:DescribeLaunchTemplateVersions",
            "autoscaling:DescribeTags",
            "autoscaling:DescribeLaunchConfigurations",
            "ec2:DescribeInstanceTypes",
          ]
          Resource = "*"

        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "aws_eks_autoscaler_policies" {
  role       = aws_iam_role.aws_eks_cluster_auto_scaler.name
  policy_arn = aws_iam_policy.aws_eks_cluster_auto_scaler.arn
}
