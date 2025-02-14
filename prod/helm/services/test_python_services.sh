#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export K8S_VERSION=1.25

./prod/helm/services/infosite/infosite/test.sh
./prod/helm/services/webhooks/webhooks/test.sh
./prod/helm/services/users/workflow/users-workflow/test.sh
./prod/helm/services/buildsense/workflow/buildsense-workflow/test.sh
./prod/helm/services/buildsense/api/buildsense-api/test.sh
./prod/helm/services/scm-integration/workflow/scm-integration-workflow/test.sh
./prod/helm/services/scm-integration/api/scm-integration-api/test.sh
./prod/helm/services/crawler/pypi/workflow/crawler-pypi-workflow/test.sh
./prod/helm/services/dependency/workflow/dependency-workflow/test.sh
./prod/helm/services/toolshed/toolshed/test.sh
./prod/helm/services/servicerouter/servicerouter/test.sh
./prod/helm/services/pants-demos/depgraph/web/pants-demos-depgraph-web/test.sh
./prod/helm/services/pants-demos/depgraph/workflow/pants-demos-depgraph-workflow/test.sh
./prod/helm/services/oss-metrics/workflow/oss-metrics-workflow/test.sh
./prod/helm/services/payments/api/payments-api/test.sh
./prod/helm/services/payments/workflow/payments-workflow/test.sh
./prod/helm/services/notifications/api/notifications-api/test.sh
./prod/helm/services/notifications/workflow/notifications-workflow/test.sh
