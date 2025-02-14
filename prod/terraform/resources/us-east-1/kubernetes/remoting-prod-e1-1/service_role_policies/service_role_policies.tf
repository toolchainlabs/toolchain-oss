# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  logging_es_domain_name = "prod-logging"
  readonly               = "${local.region}.toolchain.com-readonly"
  readwrite              = "${local.region}.toolchain.com-readwrite"

  # Names of policies required by specific services in this cluster.
  policy_map = {
    # Note that the policy does not have `.${region}.toolchain.com` in its name.
    "proxy-server" = ["auth-token-mapping-prod-readonly"]
  }

  # Transform the policy map into a list of maps containing the service/policy attributes.
  _policy_map_transformed = flatten([
    for service, policies in local.policy_map : [
      for policy in policies : {
        service = service
        policy  = policy
      }
    ]
  ])

  # Finally, transform that into a map from SERVICE::POLICY to the map of attributes.
  # Since each SERVICE::POLICY value is unique, this allows using `for_each` below in
  # the aws_iam_role_policy_attachment resource. This means additions to `policy_map` will
  # not result in destroying and recreating existing service/policy attachments.
  _policy_map_by_service_policy = {
    for service_policy in local._policy_map_transformed :
    "${service_policy["service"]}::${service_policy["policy"]}" => service_policy
  }
}

resource "aws_iam_role_policy_attachment" "service_role_policies" {
  for_each = local._policy_map_by_service_policy

  role       = "k8s.${local.cluster}.${replace(each.value["service"], "/", "-")}.service"
  policy_arn = "arn:aws:iam::${local.account_id}:policy/${each.value["policy"]}"
}
