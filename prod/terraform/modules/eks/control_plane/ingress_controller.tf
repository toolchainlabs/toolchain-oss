# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Resources required for running the AWS ALB ingress controller on the cluster.


# The role that expresses the permissions required by the AWS ALB ingress controller.
# The policy allows it to be associates the role w/ a k8s service account `aws-alb-ingress-controller` defined in the k8s `kube-system` namespace.
resource "aws_iam_role" "ingress_controller" {
  count                 = var.has_ingress ? 1 : 0
  name                  = "k8s.${var.cluster_name}.ingress"
  force_detach_policies = false
  tags                  = var.extra_tags
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Federated = local.oidc_provider_arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            # see: prod/helm/aws/aws-alb-ingress-controller/values.yaml
            "${local.oidc_provider}:sub" : "system:serviceaccount:kube-system:aws-alb-ingress-controller"
          }
        }
      }
    ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "k8s_aws_ingress_controller_policy" {
  count      = var.has_ingress ? 1 : 0
  role       = aws_iam_role.ingress_controller[count.index].name
  policy_arn = data.terraform_remote_state.global.outputs.k8s_aws_ingress_controller_policy_arn
}

# The role that expresses the AWS permissions required by ExternalDNS.
# See https://github.com/kubernetes-incubator/external-dns.
# The policy allows it to be associates the role w/ a k8s service account `external-dns` defined in the k8s `kube-system` namespace.
resource "aws_iam_role" "external_dns" {
  count                 = var.has_ingress ? 1 : 0
  name                  = "k8s.${var.cluster_name}.external-dns"
  force_detach_policies = false
  tags                  = var.extra_tags
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
              # see: prod/helm/aws/external-dns/values.yaml
              "${local.oidc_provider}:sub" : "system:serviceaccount:kube-system:external-dns"
            }
          }
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "k8s_aws_external_dns_policy" {
  count      = var.has_ingress ? 1 : 0
  role       = aws_iam_role.external_dns[count.index].name
  policy_arn = data.terraform_remote_state.global.outputs.k8s_aws_external_dns_policy_arn
}
