# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "aws_acm_certificate" "domain_cert" {
  count    = var.custom_domain == "" ? 0 : 1
  domain   = var.custom_domain
  statuses = ["ISSUED"]
}

locals {
  tags = merge(var.extra_tags, { toolchain_cost_center = var.tag_cost_center })
}

resource "aws_opensearch_domain" "es_domain" {
  domain_name    = var.domain_name
  engine_version = "OpenSearch_2.3"
  encrypt_at_rest {
    enabled = false
  }
  tags = local.tags
  cluster_config {
    instance_type          = var.instance_type
    instance_count         = var.instance_count
    zone_awareness_enabled = true
    zone_awareness_config {
      availability_zone_count = var.az_count
    }

    dedicated_master_enabled = var.dedicated_master_enabled
    # Hard coded values for now, we can move to variables if we need to.
    dedicated_master_count = var.dedicated_master_enabled ? 3 : null
    dedicated_master_type  = var.dedicated_master_enabled ? "m6g.large.search" : null
  }
  vpc_options {
    security_group_ids = [aws_security_group.es.id]
    subnet_ids         = module.es_subnet.ids
  }
  snapshot_options {
    automated_snapshot_start_hour = 8
  }
  ebs_options {
    volume_type = var.ebs_type
    volume_size = var.ebs_size
    ebs_enabled = true
  }
  access_policies = var.access_policies

  dynamic "domain_endpoint_options" {
    for_each = var.custom_domain != "" ? [1] : []
    content {
      enforce_https                   = true
      custom_endpoint_enabled         = true
      custom_endpoint                 = var.custom_domain
      custom_endpoint_certificate_arn = data.aws_acm_certificate.domain_cert[0].arn
    }
  }
  dynamic "cognito_options" {
    for_each = var.cognito_options.enabled ? [1] : []
    content {
      enabled          = var.cognito_options.enabled
      user_pool_id     = var.cognito_options.user_pool_id
      identity_pool_id = var.cognito_options.identity_pool_id
      role_arn         = var.cognito_options.role_arn
    }
  }
  timeouts {
  }
}

