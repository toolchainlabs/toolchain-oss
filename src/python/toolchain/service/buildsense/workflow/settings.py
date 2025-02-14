# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.buildsense.settings_base import *  # noqa: F403
from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

set_up_databases(__name__, "buildsense", "users")
# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"buildsense🥉workflow👾{uuid.uuid4()}☠️🤖"

# since we have this model in this service and we want to make sure Django doesn't get confused
AUTH_USER_MODEL = "site.ToolchainUser"

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    if IS_RUNNING_ON_K8S:
        INFLUXDB_CONFIG = InfluxDBConnectionConfig.from_config(
            service="buildsense",
            config=config,
            secrets_reader=SECRETS_READER,
            is_read_only=False,
        )
    else:
        INFLUXDB_CONFIG = InfluxDBConnectionConfig.for_local_dev(
            service="buildsense", secrets_reader=SECRETS_READER, is_read_only=False
        )
