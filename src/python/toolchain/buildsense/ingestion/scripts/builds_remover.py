# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.aws.s3 import S3
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable

_logger = logging.getLogger(__name__)


class BuildsRemover:
    @classmethod
    def for_django_command(cls, django_settings, dry_run):
        return cls(
            aws_region=django_settings.AWS_REGION,
            bucket_name=django_settings.BUILDSENSE_BUCKET,
            bucket_path=django_settings.BUILDSENSE_STORAGE_BASE_S3_PATH,
            env_name=django_settings.TOOLCHAIN_ENV.get_env_name(),
            dry_run=dry_run,
        )

    def __init__(self, *, aws_region, bucket_name, bucket_path, env_name, dry_run):
        self._s3 = S3(aws_region)
        self._bucket_name = bucket_name
        self._env_name = env_name
        self._bucket_path = bucket_path
        self._dry_run = dry_run

    def _remove_build(self, s3_key_dict):
        dry_run_str = "[Dry]" if self._dry_run else ""
        s3_key = s3_key_dict["Key"]
        key_parts = s3_key.split("/")
        if "duplicates" in key_parts:
            return
        customer_id = key_parts[2]
        repo_id = key_parts[3]
        user_api_id = key_parts[4]
        run_id = key_parts[5]

        run_info_table = RunInfoTable.for_customer_id(customer_id=customer_id, allow_overwrites=False)
        partition_key, partition_value = run_info_table._get_user_partition_info(repo_id, user_api_id)
        key = {partition_key: partition_value, "run_id": run_id}
        dynamo_table = run_info_table._get_table()
        row_key = dynamo_table._converter.convert_item(key)
        _logger.info(f"{dry_run_str} Delete build for {key} {s3_key}")
        if not self._dry_run:
            dynamo_table._client.delete_item(TableName=dynamo_table._table_name, Key=row_key)
            self._s3.delete_object(bucket=self._bucket_name, key=s3_key)

    def delete_builds_for_key(self, prefix: str) -> int:
        count = 0
        for s3_key_dict in self._s3.key_metadata_with_prefix(
            bucket=self._bucket_name, key_prefix=f"{self._bucket_path}/{prefix}"
        ):
            count += 1
            self._remove_build(s3_key_dict=s3_key_dict)
        return count
