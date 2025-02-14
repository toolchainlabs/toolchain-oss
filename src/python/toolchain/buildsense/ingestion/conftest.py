# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.buildsense.constants import BUILDSENSE_API_MIDDLEWARE
from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.django.site.settings.util import get_rest_framework_config
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.util.test.elastic_search_util import DummyElasticRequests

_APPS = [
    "toolchain.workflow.apps.WorkflowAppConfig",
    "toolchain.buildsense.apps.BuildSenseAppConfig",
    "toolchain.buildsense.ingestion.apps.BuildDataIngestionAppConfig",
]
_APPS.extend(USERS_DB_DJANGO_APPS)

_SETTINGS = dict(
    MIDDLEWARE=BUILDSENSE_API_MIDDLEWARE,
    ROOT_URLCONF="toolchain.buildsense.urls_api",
    RUN_INFO_DYNAMODB_TABLE_NAME="test-runinfo-v1",
    BUILDSENSE_BUCKET="fake-test-buildsense-bucket",
    REST_FRAMEWORK=get_rest_framework_config(),
    BUILDSENSE_STORAGE_BASE_S3_PATH="no-soup-for-you/buildsense/storage",
    BUILDSENSE_QUEUE_BASE_S3_PATH="bad-chicken/mess-u-up",
    IS_RUNNING_ON_K8S=True,
    NAMESPACE="tinsel",
    INFLUXDB_CONFIG=InfluxDBConnectionConfig(org_name="buildsense", host="jerry.festivus", token="pirate", port=9911),
    ELASTICSEARCH_CONFIG=BuildSenseElasticSearchConfig.for_tests(DummyElasticRequests.factory),
    CSRF_USE_SESSIONS=False,
)

APPS_UNDER_TEST.extend(_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
