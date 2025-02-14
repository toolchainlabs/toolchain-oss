# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

data "pagerduty_vendor" "prometheus" {
  name = "Prometheus"
}

data "pagerduty_schedule" "schedule" {
  name = var.schedule_name
}

resource "pagerduty_escalation_policy" "policy" {
  name      = "Escalation Policy for ${var.service_name}"
  num_loops = 3

  rule {
    escalation_delay_in_minutes = 15
    target {
      type = "schedule_reference"
      id   = data.pagerduty_schedule.schedule.id
    }
  }
}

resource "pagerduty_service" "service" {
  name                    = var.service_name
  description             = var.service_description
  auto_resolve_timeout    = 14400
  acknowledgement_timeout = 600
  escalation_policy       = pagerduty_escalation_policy.policy.id
  alert_creation          = "create_alerts_and_incidents"
}


resource "pagerduty_service_integration" "prometheus" {
  name    = "prometheus-alert-mgr"
  type    = "events_api_v2_inbound_integration"
  service = pagerduty_service.service.id
}

output "service_id" {
  value = pagerduty_service.service.id
}

