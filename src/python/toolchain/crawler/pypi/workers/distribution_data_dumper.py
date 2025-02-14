# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import gzip
import json
import logging

from toolchain.aws.s3 import S3
from toolchain.crawler.base.crawler_worker_base import CrawlerWorkerBase
from toolchain.crawler.pypi.models import DumpDistributionData
from toolchain.packagerepo.pypi.models import DistributionData

_logger = logging.getLogger(__name__)


class DistributionDataDumper(CrawlerWorkerBase):
    """Dump some useful data for a PythonDistribution to S3."""

    work_unit_payload_cls = DumpDistributionData

    def do_work(self, work_unit_payload: DumpDistributionData) -> bool:
        serial_from = work_unit_payload.serial_from
        serial_to = work_unit_payload.serial_to
        data = DistributionData.get_data_shard(
            work_unit_payload.shard, work_unit_payload.num_shards, serial_from, serial_to
        )
        data_bytes = gzip.compress(json.dumps(data).encode())
        key = f"{work_unit_payload.key_prefix}{work_unit_payload.shard:04}.json.gz"
        _logger.info(f"Upload distribution data dump {serial_from=} {serial_to=} to s3: {key=} {len(data_bytes)=:,}")
        S3().upload_content(work_unit_payload.bucket, key, data_bytes)
        return True

    def on_success(self, work_unit_payload: DumpDistributionData) -> None:
        # Ensure that the next shard's work is scheduled.
        # This allows us to control how many shards run concurrently (and so how much load we put on the db).
        # E.g., if we initially schedule just shard 0, then we'll get one concurrent shard. If we initially
        # schedule shards 0, 64, 128, 192 (with num_shards=256) we'll get 4 concurrent shards, etc.
        # Note that we only schedule the next shard after this one succeeds, but we may want to change that in the future.
        next_shard = work_unit_payload.shard + 1
        if 0 <= next_shard < work_unit_payload.num_shards:
            DumpDistributionData.objects.get_or_create(
                shard=next_shard,
                num_shards=work_unit_payload.num_shards,
                bucket=work_unit_payload.bucket,
                serial_from=work_unit_payload.serial_from,
                serial_to=work_unit_payload.serial_to,
                key_prefix=work_unit_payload.key_prefix,
            )
