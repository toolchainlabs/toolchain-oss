# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.django.site.settings.service import *  # noqa: F403

_logger = logging.getLogger(__name__)

INSTALLED_APPS.extend(
    [
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.buildsense.apps.BuildSenseAppConfig",
        "toolchain.buildsense.ingestion.apps.BuildDataIngestionAppConfig",
    ]
)


if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    ELASTICSEARCH_CONFIG = BuildSenseElasticSearchConfig.for_env(
        toolchain_env=TOOLCHAIN_ENV, is_k8s=IS_RUNNING_ON_K8S, config=config
    )

if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    BUILDSENSE_BUCKET = config.get("BUILDSENSE_BUCKET", f"staging.buildstats-dev.{AWS_REGION}.toolchain.com")
    BUILDSENSE_STORAGE_BASE_S3_PATH = os.path.join(NAMESPACE, "buildstatsv1")
    BUILDSENSE_QUEUE_BASE_S3_PATH = os.path.join(NAMESPACE, "dev", "v2", "buildsense", "batches")
    RUN_INFO_DYNAMODB_TABLE_NAME = "dev-runinfo-v1"

elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    BUILDSENSE_BUCKET = config["BUILDSENSE_BUCKET"]
    BUILDSENSE_STORAGE_BASE_S3_PATH = os.path.join("prod", "v1", "buildsense")
    BUILDSENSE_QUEUE_BASE_S3_PATH = os.path.join("prod", "v1", "batches")
    RUN_INFO_DYNAMODB_TABLE_NAME = "prod-runinfo-v1"
