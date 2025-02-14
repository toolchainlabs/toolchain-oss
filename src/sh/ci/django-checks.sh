#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

pants run src/python/toolchain/service/users/api:users-api-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/users/ui:users-ui-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/scm_integration/api:scm-integration-api-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/buildsense/api:buildsense-api-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/buildsense/workflow:buildsense-worker-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/toolshed:toolshed-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/infosite:infosite-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/webhooks:webhooks-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/oss_metrics/workflow:oss-metrics-worker-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/pants_demos/depgraph/web:pants-demos-depgraph-web-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/pants_demos/depgraph/workflow:pants-demos-depgraph-worker-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/payments/workflow:payments-worker-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/payments/api:payments-api-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/notifications/workflow:notifications-worker-manage -- check --fail-level WARNING
pants run src/python/toolchain/service/notifications/api:notifications-api-manage -- check --fail-level WARNING
