# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

module "grafana_certificate" {
  source      = "../../modules/acm"
  hosted_zone = "toolchainlabs.com"
  domain_name = "grafana.toolchainlabs.com"
}
