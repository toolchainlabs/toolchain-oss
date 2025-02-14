#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import itertools
import logging
import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import cast

import redis

from toolchain.aws.elasticache import ElastiCache
from toolchain.aws.s3 import S3
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


# NB: It is important for this class to not use Redis APIs which affect access times (IDLETIME).
class RedisKeysDumper:
    def __init__(
        self,
        aws_region: str,
        redis_cluster_prefix: str,
        s3_url: str | None = None,
        output_path: Path | None = None,
    ) -> None:
        self._aws_region = aws_region
        self._s3_url = s3_url
        self._output = output_path
        self._redis_cluster_id_prefix = redis_cluster_prefix
        self._ec = ElastiCache(aws_region)

    def _get_redis_key_names(self, redis_client: redis.Redis) -> set[str]:
        _logger.info(f"Retrieving key names from Redis {redis_client!r}.")
        keys = set()
        for key in redis_client.scan_iter():
            keys.add(cast(bytes, key).decode())
        _logger.info(f"Retrieved {len(keys):,} key names from Redis.")
        return keys

    def _get_sizes_of_keys(self, redis_name: str, redis_client: redis.Redis, keys: set[str]) -> dict[str, int]:
        _logger.info(f"Retrieving sizes of the cache entries {redis_name}.")
        key_to_size = {}
        for keys_batch in grouper(keys, 1000):
            pipeline = redis_client.pipeline(transaction=False)
            keys_sent_to_redis = []
            for key in keys_batch:
                if not key:  # skip padding in final batch
                    continue
                keys_sent_to_redis.append(key)
                pipeline.memory_usage(key)

            size_results = pipeline.execute()
            for key, size in zip(keys_sent_to_redis, size_results):
                # note: memory_usage returns Redis `nil` if the key does not exist
                if size is not None:
                    key_to_size[key] = size
        _logger.info(f"Retrieved sizes of the cache entries {redis_name} {len(key_to_size):,} keys.")
        return key_to_size

    def write_to_s3(self, s3_bucket: str, s3_key: str, content: bytes, metadata: dict[str, str] | None = None) -> str:
        s3 = S3(self._aws_region)
        _logger.info(f"Uploading redis keys data to bucket {s3_bucket} at {s3_key} {metadata=}.")
        s3.upload_content(
            bucket=s3_bucket, key=s3_key, content_bytes=content, content_type="text/csv", metadata=metadata
        )
        return s3_key

    def dump_keys(self, redis_host: str, redis_port: int) -> bytes:
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
        keys = self._get_redis_key_names(redis_client)
        key_to_size = self._get_sizes_of_keys(redis_name=redis_host, redis_client=redis_client, keys=keys)
        return "\n".join([f"{key},{size}" for key, size in key_to_size.items()]).encode()

    def analyze_and_dump(self, metadata: dict[str, str] | None = None) -> tuple[str, ...]:
        redis_clusters = self._ec.get_redis_clusters(re.compile(f"{self._redis_cluster_id_prefix}*."))
        if not redis_clusters:
            raise ToolchainAssertion(f"No redis clusters found. prefix: {self._redis_cluster_id_prefix}")
        if self._s3_url:
            s3_bucket, base_key = S3.parse_s3_url(self._s3_url)
            s3_key_path: Path | None = Path(base_key) / utcnow().strftime("%Y-%m-%d-%H:%S")
        else:
            s3_bucket = s3_key_path = None  # type: ignore[assignment]
        keys: list[str] = []
        for cluster in redis_clusters:
            content = self.dump_keys(redis_host=cluster.address, redis_port=cluster.port)
            if self._output:
                size = self._output.write_bytes(content)
                _logger.info(f"Output written to {self._output} {size:,} bytes")
            elif s3_key_path and s3_bucket:
                s3_key = (s3_key_path / f"{cluster.clustrer_id}.csv").as_posix()
                self.write_to_s3(s3_bucket=s3_bucket, s3_key=s3_key, content=content, metadata=metadata)
                keys.append(s3_key)
        return tuple(keys)


class DumpRedisMetadata(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        if cmd_args.write_to_s3_base_path is not None and cmd_args.output is not None:
            raise ToolchainAssertion("--write-to-s3-base-path and --output are mutually exclusive")
        output_path = Path(cmd_args.output) if cmd_args.output else None
        if not output_path and not cmd_args.s3_base_path:
            raise ToolchainAssertion("Must specify one of --write-to-s3-base-path or --output")
        self._dumper = RedisKeysDumper(
            aws_region=cmd_args.aws_region,
            s3_url=cmd_args.s3_base_path,
            redis_cluster_prefix=cmd_args.redis_cluster_prefix,
            output_path=output_path,
        )

    def run(self) -> int:
        self._dumper.analyze_and_dump()
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        super().add_aws_region_argument(parser)
        parser.add_argument("--redis-cluster-prefix", required=True, type=str, help="Redis cluster id prefix")
        parser.add_argument(
            "--write-to-s3-base-path", type=str, default=None, help="S3 base path in which to store the data"
        )
        parser.add_argument("--output", type=str, default=None, help="Local filename in which to store the data")


if __name__ == "__main__":
    DumpRedisMetadata.start()
