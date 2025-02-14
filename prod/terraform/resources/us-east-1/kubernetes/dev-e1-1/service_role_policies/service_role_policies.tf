# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

module "run_info_dev_table" {
  source     = "../../../../../modules/dynamodb/table"
  table_name = "dev-runinfo-v1"
}

locals {
  es_domain_name = "es-dev-1"
  readonly       = "${local.region}.toolchain.com-readonly"
  readwrite      = "${local.region}.toolchain.com-readwrite"

  # Names of policies required by specific services in this cluster.
  policy_map = {
    "buildsense/api" = [
      "staging.buildstats-dev.${local.readwrite}",
      module.run_info_dev_table.policy_name,
      "elasticsearch.${local.es_domain_name}.readwrite",
    ]
    "buildsense/workflow" = [
      "staging.buildstats-dev.${local.readwrite}",
      module.run_info_dev_table.policy_name,
      "elasticsearch.${local.es_domain_name}.readonly",
    ]
    "fluent-bit"                    = ["elasticsearch.${local.es_domain_name}.readwrite"]
    "users/workflow"                = ["send-email", "auth-token-mapping-dev-readwrite"]
    "servicerouter"                 = ["assets-dev.${local.readonly}"]
    "scm-integration/workflow"      = ["scm-integration-dev.${local.readwrite}"]
    "scm-integration/api"           = ["scm-integration-dev.${local.readwrite}"]
    "pants-demos/depgraph/web"      = ["pants-demos-dev.${local.readonly}", "assets-dev.${local.readonly}"]
    "pants-demos/depgraph/workflow" = ["pants-demos-dev.${local.readwrite}"]
    "toolshed"                      = ["pants-demos-dev.${local.readonly}"]
    "oss-metrics/workflow"          = ["bugout-dev.${local.readwrite}", "scm-integration-dev.${local.readonly}"]
    "notifications/workflow"        = ["email-dev.${local.readwrite}", "send-email"]
    "notifications/api"             = ["email-dev.${local.readonly}"]

    # Note that the policy does not have `.${region}.toolchain.com` in its name.
    "proxy-server" = ["auth-token-mapping-dev-readonly"]

    # Not used right now
    # "crawler/pypi/workflow" = ["pypi-dev.${local.readwrite}"]
    # "dependency/api"        = ["pypi-dev.${local.readonly}"]
    # "dependency/workflow"   = ["pypi-dev.${local.readonly}"]
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
  for_each   = local._policy_map_by_service_policy
  role       = "k8s.${local.cluster}.${replace(each.value["service"], "/", "-")}.service"
  policy_arn = "arn:aws:iam::${local.account_id}:policy/${each.value["policy"]}"
}
