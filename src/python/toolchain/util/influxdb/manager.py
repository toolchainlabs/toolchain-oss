# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from influxdb_client import Bucket, BucketRetentionRules

from toolchain.util.influxdb.client import InfluxDBConnectionConfig, get_client

_logger = logging.getLogger(__name__)


class MetricsStoreManager:
    def __init__(self, config: InfluxDBConnectionConfig, bucket_name: str) -> None:
        self._influxdb_org_id = config.org_id
        self._client = get_client(config)
        self._bucket_name = bucket_name

    def init_bucket(self, recreate: bool = False, retention_days: int = 0) -> bool:
        created, bucket = self._create_bucket(self._bucket_name, recreate=recreate, retention_days=retention_days)
        if created:
            _logger.info(f"Create bucket {self._bucket_name} bucket_id={bucket.id}")
        else:
            _logger.info(f"bucket already exists {self._bucket_name} bucket_id={bucket.id}")
            if retention_days:
                self._set_bucket_retention(bucket, retention_days)
        return created

    def delete_bucket(self) -> bool:
        bucket_name = self._bucket_name
        api = self._client.buckets_api()
        bucket = api.find_bucket_by_name(bucket_name=bucket_name)
        if bucket:
            _logger.info(f"delete {bucket_name=} bucket_id={bucket.id}")
            api.delete_bucket(bucket)
        else:
            _logger.warning(f"bucket {bucket_name=} not found.")
        return bool(bucket)

    def _get_retention_rules(self, retention_days: int) -> list[BucketRetentionRules]:
        return [
            BucketRetentionRules(
                type="expire", every_seconds=int(datetime.timedelta(days=retention_days).total_seconds())
            )
        ]

    def _create_bucket(self, bucket_name: str, recreate: bool, retention_days: int) -> tuple[bool, Bucket]:
        api = self._client.buckets_api()
        bucket = api.find_bucket_by_name(bucket_name=bucket_name)
        if bucket is not None:
            if not recreate:
                return False, bucket
            _logger.info(f"delete {bucket_name=}")
            api.delete_bucket(bucket)
        retention_rules = self._get_retention_rules(retention_days) if retention_days else None
        new_bucket = api.create_bucket(
            bucket_name=bucket_name, org=self._influxdb_org_id, retention_rules=retention_rules
        )
        return True, new_bucket

    def _set_bucket_retention(self, bucket: Bucket, retention_days: int) -> None:
        api = self._client.buckets_api()
        bucket.retention_rules = self._get_retention_rules(retention_days)
        _logger.info(
            f"set_bucket_retention: {self._bucket_name} bucket_id={bucket.id}: seconds={bucket.retention_rules[0].every_seconds}"
        )
        api.update_bucket(bucket)
