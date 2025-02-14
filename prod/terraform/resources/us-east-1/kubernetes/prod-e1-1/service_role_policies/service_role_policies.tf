# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

module "run_info_prod_table" {
  source     = "../../../../../modules/dynamodb/table"
  table_name = "prod-runinfo-v1"
}

locals {
  buildsense_es_domain_name = "prod-buildsense"
  logging_es_domain_name    = "prod-logging"
  readonly                  = "${local.region}.toolchain.com-readonly"
  readwrite                 = "${local.region}.toolchain.com-readwrite"

  # Names of policies required by specific services in this cluster.
  policy_map = {
    "buildsense/workflow" = [
      "builds.buildsense.${local.readwrite}",
      module.run_info_prod_table.policy_name,
      "elasticsearch.${local.buildsense_es_domain_name}.readonly"
    ]
    "buildsense/api" = [
      "builds.buildsense.${local.readwrite}",
      module.run_info_prod_table.policy_name,
      "elasticsearch.${local.buildsense_es_domain_name}.readwrite"
    ]
    "crawler/pypi/workflow"         = ["pypi.${local.readwrite}"]
    "dependency/workflow"           = ["pypi.${local.readonly}"]
    "dependency/api"                = ["pypi.${local.readonly}"]
    "users/workflow"                = ["artifacts.${local.readwrite}", "send-email", "auth-token-mapping-prod-readwrite"]
    "servicerouter"                 = ["assets.${local.readonly}"]
    "scm-integration/workflow"      = ["scm-integration.${local.readwrite}"]
    "scm-integration/api"           = ["scm-integration.${local.readwrite}"]
    "toolshed"                      = ["pants-demos.${local.readonly}"]
    "oss-metrics/workflow"          = ["bugout-prod.${local.readwrite}", "scm-integration.${local.readonly}"]
    "pants-demos/depgraph/web"      = ["pants-demos.${local.readonly}", "assets.${local.readonly}"]
    "pants-demos/depgraph/workflow" = ["pants-demos.${local.readwrite}"]
    "notifications/workflow"        = ["email-prod.${local.readwrite}", "send-email"]
    "notifications/api"             = ["email-prod.${local.readonly}"]
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
    for role_policy in local._policy_map_transformed :
    "${role_policy["service"]}::${role_policy["policy"]}" => role_policy
  }
}

resource "aws_iam_role_policy_attachment" "service_role_policies" {
  for_each = local._policy_map_by_service_policy

  role       = "k8s.${local.cluster}.${replace(each.value["service"], "/", "-")}.service"
  policy_arn = "arn:aws:iam::${local.account_id}:policy/${each.value["policy"]}"
}
