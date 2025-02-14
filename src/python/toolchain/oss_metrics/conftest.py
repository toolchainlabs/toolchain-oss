# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
import logging.config

from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor

_sr = DummySecretsAccessor.create_rotatable()
_sr.set_secret("bugout-api-key", json.dumps({"api-key": "summer of george"}))

_SETTINGS = dict(
    SECRETS_READER=_sr,
    BUGOUT_INTEGRATION_BUCKET="festivus-bugout-bucket",
    BUGOUT_STORE_BASE_KEY="european/carry-all",
    GITHUB_REPO_STATS_BASE_KEY="no-bagel/yamahama",
    SCM_INTEGRATION_BUCKET="festivus-scm-bucket",
    INFLUXDB_CONFIG=InfluxDBConnectionConfig(
        org_name="pants-telemetry", host="jerry.festivus", token="pirate", port=9911
    ),
)


_APPS = [
    "toolchain.oss_metrics.bugout_integration.apps.BugoutIntegrationAppConfig",
    "toolchain.oss_metrics.apps.OssMetricsAppConfig",
    "toolchain.workflow.apps.WorkflowAppConfig",
]


APPS_UNDER_TEST.extend(_APPS)
EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
