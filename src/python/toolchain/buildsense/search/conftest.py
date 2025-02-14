# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.util.test.elastic_search_util import DummyElasticRequests

_APPS = [
    "django.contrib.auth",
    "toolchain.django.site",
    # Because we use test_utils.data_loader under tests.
    "toolchain.workflow.apps.WorkflowAppConfig",
    "toolchain.buildsense.apps.BuildSenseAppConfig",
    "toolchain.buildsense.ingestion.apps.BuildDataIngestionAppConfig",
]

_SETTINGS = dict(
    RUN_INFO_DYNAMODB_TABLE_NAME="test-runinfo-v1",
    ELASTICSEARCH_CONFIG=BuildSenseElasticSearchConfig.for_tests(DummyElasticRequests.factory),
)

APPS_UNDER_TEST.extend(_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
