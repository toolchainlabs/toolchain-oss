# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.buildsense.constants import BUILDSENSE_API_MIDDLEWARE
from toolchain.buildsense.settings_base import *  # noqa: F403
from toolchain.django.site.settings.util import get_rest_framework_config
from toolchain.util.influxdb.client import InfluxDBConnectionConfig

set_up_databases(__name__, "users", "buildsense")
MIDDLEWARE = BUILDSENSE_API_MIDDLEWARE
ROOT_URLCONF = "toolchain.service.buildsense.api.urls"
REST_FRAMEWORK = get_rest_framework_config()
INSTALLED_APPS.append("toolchain.workflow.apps.WorkflowAppConfig")
AUTH_USER_MODEL = "site.ToolchainUser"

# We will eventually get rid of it, once we no longer use django sessions in this service
if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    SECRET_KEY = SECRETS_READER.get_secret_or_raise("django-secret-key")
    if IS_RUNNING_ON_K8S:
        INFLUXDB_CONFIG = InfluxDBConnectionConfig.from_config(
            service="buildsense",
            config=config,
            secrets_reader=SECRETS_READER,
            is_read_only=True,
        )
    else:
        INFLUXDB_CONFIG = InfluxDBConnectionConfig.for_local_dev(
            service="buildsense", secrets_reader=SECRETS_READER, is_read_only=True
        )

else:
    SECRET_KEY = "buildsense🎰fake🧄🥔-secret🧅key🫒"

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 10  # 10mb, needed for buildsense batch
BOTO3_CONFIG = {
    "dynamodb": {
        # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html#defining-a-retry-configuration-in-a-config-object-for-your-boto3-client
        # Defaults are defined in botocore/data/_retry.json
        "retries": {"max_attempts": 2, "mode": "standard"},
    }
}
