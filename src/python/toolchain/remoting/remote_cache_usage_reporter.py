#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import csv
import json
import logging
import math
import tempfile
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from humanize.filesize import naturalsize
from prometheus_client import CollectorRegistry, Gauge, Histogram, push_to_gateway

from toolchain.aws.s3 import S3
from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.remoting.dump_redis_metadata import RedisKeysDumper
from toolchain.util.config.kubernetes_env import KubernetesEnv
from toolchain.util.prod.chat_client import ChatClient
from toolchain.util.secret.secrets_accessor import KubernetesVolumeSecretsReader

_logger = logging.getLogger(__name__)


@dataclass
class CustomerUsageEntry:
    customer_id: str
    customer_name: str
    usage_bytes: int
    entries_count: int

    def add_usage(self, entries_count: int, usage_bytes: int) -> None:
        self.entries_count += entries_count
        self.usage_bytes += usage_bytes


class CustomersMap:
    @classmethod
    def load_from_s3(cls, aws_region: str, s3_url: str) -> CustomersMap:
        s3_bucket, s3_key = S3.parse_s3_url(s3_url)
        content = S3(region=aws_region).get_content(s3_bucket, s3_key)
        customers_map = json.loads(content)
        _logger.info(f"loaded customers map: {s3_url=} customers: {len(customers_map)}")
        return cls(customers_map)

    @classmethod
    def empty_map(cls) -> CustomersMap:
        return cls({})

    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    @property
    def count(self) -> int:
        return len(self._data)

    def get_customer_name(self, customer_id: str) -> str:
        return self._data.get(customer_id, customer_id)


class RedisKeysAnalyzer:
    def __init__(self, aws_region: str, bucket: str, customers_map: CustomersMap) -> None:
        self._s3 = S3(region=aws_region)
        self._s3_bucket = bucket
        self._customers = customers_map

    def to_customer_id(self, key: str) -> str:
        customer_id = key.split("-")[1]
        if ":" in customer_id:
            customer_id, *_ = customer_id.partition(":")
        return customer_id

    def analyze_usage(self, s3_keys: tuple[str, ...]) -> list[CustomerUsageEntry]:
        usage_by_customer: dict[str, CustomerUsageEntry] = {}
        for s3_key in s3_keys:
            with tempfile.TemporaryDirectory() as td:
                data_file = Path(td) / "data.csv"
                self._s3.download_file(bucket=self._s3_bucket, key=s3_key, path=data_file.as_posix())
                _logger.info(f"analyze redis usage: {s3_key=} size: {data_file.stat().st_size:,} bytes")
                self.read_csv(data_file, usage_by_customer)
        _logger.info(f"analyzed {len(usage_by_customer)} customers in redis.")
        return sorted(usage_by_customer.values(), key=lambda usage: usage.usage_bytes, reverse=True)

    def read_csv(self, data_file: Path, usage_by_customer: dict[str, CustomerUsageEntry]) -> None:
        customer_ids_to_key_size: dict[str, int] = defaultdict(int)
        customer_ids_keys_count: dict[str, int] = defaultdict(int)

        with data_file.open() as data_csv:
            for row in csv.reader(data_csv):
                key = row[0]
                size = int(row[1])
                customer_id = self.to_customer_id(key)
                customer_ids_to_key_size[customer_id] += size
                customer_ids_keys_count[customer_id] += 1

        for customer_id, keys_count in customer_ids_keys_count.items():
            usage_bytes = customer_ids_to_key_size[customer_id]
            if customer_id not in usage_by_customer:
                usage_by_customer[customer_id] = CustomerUsageEntry(
                    customer_id=customer_id,
                    customer_name=self._customers.get_customer_name(customer_id),
                    usage_bytes=usage_bytes,
                    entries_count=keys_count,
                )
            else:
                usage_by_customer[customer_id].add_usage(keys_count, usage_bytes)


class FileStorageAnalyzer:
    def __init__(self, base_path: Path, customers_map: CustomersMap) -> None:
        _logger.info(f"FileStorageAnalyzer {base_path=} customers in map: {customers_map.count}")
        self._base_path = base_path
        self._customers = customers_map

    def analyze_usage(self) -> list[CustomerUsageEntry]:
        _logger.info("analyze File stoage usage")
        usage_entries = self.get_usage_entries()
        _logger.info(f"analyzed {len(usage_entries)} customer efs usage.")
        return usage_entries

    def get_usage_entries(self) -> list[CustomerUsageEntry]:
        usage_entries = []
        for customer_path in self._base_path.iterdir():
            if not customer_path.is_dir():
                continue
            customer_name = self._customers.get_customer_name(customer_path.name)
            _logger.info(f"check EFS usage for {customer_name} ({customer_path.as_posix()})")
            with Timer() as timer:
                sizes = [f.stat().st_size for f in customer_path.glob("**/*") if f.is_file()]
            _logger.info(f"EFS usage for {customer_name} files={len(sizes):,} took={timer.elapsed:.3f} sec")
            usage_entries.append(
                CustomerUsageEntry(
                    customer_id=customer_path.name,
                    customer_name=customer_name,
                    usage_bytes=sum(sizes),
                    entries_count=len(sizes),
                )
            )
        return usage_entries


class Metrics:
    def __init__(self, push_gateway_url: str | None) -> None:
        k8s_env = KubernetesEnv.from_env()
        self._push_gateway_url = push_gateway_url
        self._registry = CollectorRegistry()
        self._labels_values = {
            "pod": k8s_env.pod_name,
            "namespace": k8s_env.namespace,
        }
        usage_labels = list(self._labels_values.keys())
        usage_labels.extend(("customer", "storage_type"))
        self._bytes_usage = Gauge(
            name="toolchain_remote_cache_usage_bytes",
            documentation="Number of used bytes in remote cache by customer",
            registry=self._registry,
            labelnames=usage_labels,
        )
        self._entries_count = Gauge(
            name="toolchain_remote_cache_objects_count",
            documentation="Number of used bytes in remote cache by customer",
            registry=self._registry,
            labelnames=usage_labels,
        )
        self._run_time = Histogram(
            name="toolchain_remote_cache_dump_latency",
            documentation="Histogram job run time.",
            registry=self._registry,
            labelnames=list(self._labels_values.keys()),
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 90.0, 120.0, 300.0, float("inf")),
        )

    @contextmanager
    def measure_latency(self):
        with self._run_time.labels(**self._labels_values).time():
            yield self

    def track_cache_usage(self, usage_data: list[CustomerUsageEntry], storage_type: str) -> None:
        for usage_entry in usage_data:
            self._bytes_usage.labels(
                customer=usage_entry.customer_name, storage_type=storage_type, **self._labels_values
            ).set(usage_entry.usage_bytes)

            self._entries_count.labels(
                customer=usage_entry.customer_name, storage_type=storage_type, **self._labels_values
            ).set(usage_entry.entries_count)

    def finish(self):
        if not self._push_gateway_url:
            return
        push_to_gateway(self._push_gateway_url, job="remote_cache_usage_reporter", registry=self._registry)


class RemoteCacheUsageReporter(ToolchainBinary):
    _EFS_USAGE_COST = 0.08  # $/GB-Month https://aws.amazon.com/efs/pricing/

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._report_to_chat = (utcnow().hour == int(cmd_args.chat_report_hour)) if cmd_args.chat_report_hour else False
        _logger.info(f"RemoteCacheUsageReporter: report_to_chart={self._report_to_chat} {cmd_args=}")
        bucket, _ = S3.parse_s3_url(cmd_args.s3_base_path)
        self._dumper = RedisKeysDumper(
            aws_region=cmd_args.aws_region,
            s3_url=cmd_args.s3_base_path,
            redis_cluster_prefix=cmd_args.redis_cluster_prefix,
        )
        customers = (
            CustomersMap.load_from_s3(cmd_args.aws_region, cmd_args.customers_map_s3_url)
            if cmd_args.customers_map_s3_url
            else CustomersMap.empty_map()
        )
        self._redis_analyzer = RedisKeysAnalyzer(aws_region=cmd_args.aws_region, bucket=bucket, customers_map=customers)
        self._fs_analyzer = FileStorageAnalyzer(
            base_path=Path(cmd_args.file_system_storage_path), customers_map=customers
        )
        self._metrics = Metrics(cmd_args.push_gateway_url)

    def _get_chat(self) -> ChatClient | None:
        if not self._report_to_chat:
            return None
        slack_webhook = KubernetesVolumeSecretsReader().get_secret("slack-webhook")
        return ChatClient.for_job(job_name="Remote Cache Usage", webhook_url=slack_webhook) if slack_webhook else None

    def generate_usage_message(self, fs_usage: list[CustomerUsageEntry], redis_usage: list[CustomerUsageEntry]) -> str:
        message_lines: list[tuple[int, str]] = []
        redis_usage_map = {ent.customer_id: ent for ent in redis_usage}
        fs_usage_map = {ent.customer_id: ent for ent in fs_usage}
        for customer_id in set(fs_usage_map.keys()).union(redis_usage_map.keys()):
            fs_entry = fs_usage_map.get(customer_id)
            redis_entry = redis_usage_map.get(customer_id)
            customer_name = fs_entry.customer_name if fs_entry else redis_entry.customer_name  # type: ignore[union-attr]
            fs_bytes = fs_entry.usage_bytes if fs_entry else 0
            redis_bytes = redis_entry.usage_bytes if redis_entry else 0
            fs_objects = fs_entry.entries_count if fs_entry else 0
            redis_objects = redis_entry.entries_count if redis_entry else 0
            fs_cost = math.floor(math.floor(fs_bytes / 1024 / 1024 / 1024) * self._EFS_USAGE_COST)
            message_lines.append(
                (
                    fs_bytes + redis_bytes,
                    f"{customer_name}: {naturalsize(fs_bytes)} ${fs_cost}/mo ({fs_objects:,}) + {naturalsize(redis_bytes)} ({redis_objects:,})",
                )
            )
        message_lines = sorted(message_lines, key=lambda tp: tp[0], reverse=True)
        return "EFS + REDIS - bytes and object count\n" + "\n".join(msg for _, msg in message_lines)

    def run(self) -> int:
        chat = self._get_chat()
        metadata = {"toolchain_report": "daily" if self._report_to_chat else "hourly"}
        with self._metrics.measure_latency():
            s3_keys = self._dumper.analyze_and_dump(metadata)
        redis_usage = self._redis_analyzer.analyze_usage(s3_keys)
        fs_usage = self._fs_analyzer.analyze_usage()
        message = self.generate_usage_message(fs_usage=fs_usage, redis_usage=redis_usage)
        _logger.info(message)
        if chat:
            chat.post_message(message=message, channel=ChatClient.Channel.BACKEND)
        self._metrics.track_cache_usage(redis_usage, storage_type="redis")
        self._metrics.track_cache_usage(fs_usage, storage_type="efs")
        self._metrics.finish()
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        super().add_aws_region_argument(parser)
        parser.add_argument("--redis-cluster-prefix", required=True, type=str, help="Redis cluster id prefix")
        parser.add_argument(
            "--file-system-storage-path",
            type=str,
            required=True,
            help="Local path where to analyze cache fie system based storage.",
        )

        parser.add_argument("--s3-base-path", required=True, type=str, help="S3 base path in which to store the keys")
        parser.add_argument(
            "--customers-map-s3-url",
            required=False,
            default=None,
            type=str,
            help="S3 url to customers map",
        )
        parser.add_argument("--chat-report-hour", type=int, default=None, help="Chat report hour (UTC, hour of day)")
        parser.add_argument("--push-gateway-url", type=str, default=None, help="push gateway url")


if __name__ == "__main__":
    RemoteCacheUsageReporter.start()
