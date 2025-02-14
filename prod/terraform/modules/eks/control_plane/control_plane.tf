# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources for an EKS control plane.

# See https://learn.hashicorp.com/terraform/aws/eks-intro.

data "aws_iam_role" "eks_service_role" {
  name = "eks-service-role"
}

# Note: This is not a huge deal, but EKS does not enable the AlwaysPullImages admission policy.
# Enabling it would cause all image pulls to re-auth, which would be slightly more secure
# (e.g., a compromised pod would not be able to run other images).
# Instead we set the imagePullPolicy on our containers, which amounts to the same thing,
# assuming all pods (even if compromised) were started by us.
# See page 50 of https://kubernetes-security.info/.
resource "aws_eks_cluster" "main" {
  name                      = var.cluster_name
  role_arn                  = data.aws_iam_role.eks_service_role.arn
  version                   = "1.25" # Kubernetes master version.
  enabled_cluster_log_types = var.enable_logs ? ["api", "controllerManager", "scheduler"] : []
  vpc_config {
    subnet_ids         = concat(module.private_subnets.ids, module.public_subnets.ids)
    security_group_ids = [aws_security_group.control_plane.id]
  }
  tags = local.tags
}

resource "aws_iam_openid_connect_provider" "cluster_openid_provider" {
  # https://docs.aws.amazon.com/eks/latest/userguide/enable-iam-roles-for-service-accounts.html
  url = local.issuer_url
  # AKA audiences
  client_id_list = ["sts.amazonaws.com"]
  # Hard coded thumbprint for clusters in us-east-1. 
  # https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc_verify-thumbprint.html
  # trying to read it using the suggestion in https://github.com/hashicorp/terraform-provider-aws/issues/10104#issuecomment-534937559 
  # yields the wrong thumbprint
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
  tags            = { "cluster" : var.cluster_name }
}

locals {
  issuer_url        = aws_eks_cluster.main.identity[0].oidc[0].issuer
  issuer_id         = regex("[A-F0-9]{32}$", local.issuer_url)
  oidc_provider     = "oidc.eks.${local.region}.amazonaws.com/id/${local.issuer_id}"
  oidc_provider_arn = "arn:aws:iam::${local.account_id}:oidc-provider/oidc.eks.${local.region}.amazonaws.com/id/${local.issuer_id}"
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"
}

output "control_plane_security_group_id" {
  value = aws_security_group.control_plane.id
}

output "oidc_provider" {
  value = local.oidc_provider
}

output "oidc_provider_arn" {
  value = local.oidc_provider_arn
}