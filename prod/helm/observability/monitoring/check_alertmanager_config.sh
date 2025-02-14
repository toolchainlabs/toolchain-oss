#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

yq r prod/helm/observability/monitoring/monitoring/values.yaml prometheus-operator.alertmanager.config | sed 's/SLACK_API_URL_PLACEHOLDER/http:\/\/fakeslack.com\/path/; s/DEAD_MANS_SNITCH_URL_PLACEHOLDER/http:\/\/fake-snitch.com\/path/' | amtool check-config
