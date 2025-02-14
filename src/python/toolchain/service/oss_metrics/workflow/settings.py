# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

INSTALLED_APPS.extend(
    (
        "toolchain.oss_metrics.bugout_integration.apps.BugoutIntegrationAppConfig",
        "toolchain.oss_metrics.apps.OssMetricsAppConfig",
    )
)

# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"bugout🥉integration🤖{uuid.uuid4()}☠️👾"

set_up_databases(__name__, "oss_metrics")

if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    BUGOUT_INTEGRATION_BUCKET = config.get("BUGOUT_INTEGRATION_BUCKET", f"bugout-dev.{AWS_REGION}.toolchain.com")
    BUGOUT_STORE_BASE_KEY = os.path.join("dev", NAMESPACE)
elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    BUGOUT_INTEGRATION_BUCKET = config["BUGOUT_INTEGRATION_BUCKET"]
    BUGOUT_STORE_BASE_KEY = os.path.join("prod", "v1")

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    GITHUB_REPO_STATS_BASE_KEY = config["GITHUB_REPO_STATS_BASE_KEY"]
    SCM_INTEGRATION_BUCKET = config["SCM_INTEGRATION_BUCKET"]
    if IS_RUNNING_ON_K8S:
        INFLUXDB_CONFIG = InfluxDBConnectionConfig.from_config(
            service="pants-telemetry",
            config=config,
            secrets_reader=SECRETS_READER,
            is_read_only=False,
        )
    else:
        INFLUXDB_CONFIG = InfluxDBConnectionConfig.for_local_dev(
            service="pants-telemetry",
            secrets_reader=SECRETS_READER,
            is_read_only=False,
        )
