# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, unique
from io import BytesIO
from pathlib import PurePath
from typing import IO, Union

from django.conf import settings
from django.core.files.base import File
from prometheus_client import Histogram

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.run_processors.common import PLATFORM_INFO_FILE_NAME, WU_ARTIFACTS_FILE_NAME
from toolchain.buildsense.ingestion.utils import decompress
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.util.metrics.aws_event_adapter import PrometheusAwsMetricsAdapter

_logger = logging.getLogger(__name__)

FileMetadata = dict[str, str]
ContentOrFile = Union[bytes, IO[bytes]]

_S3_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf"))

BUILD_INFO_STORE_LATENCY = Histogram(
    name="toolchain_buildsense_ingest_s3_latency",
    documentation="Histogram of buildsense ingestion s3 store latency/time.",
    labelnames=PrometheusAwsMetricsAdapter.add_labels(),
    buckets=_S3_LATENCY_BUCKETS,
)

BUILD_INFO_LOAD_LATENCY = Histogram(
    name="toolchain_buildsense_load_s3_latency",
    documentation="Histogram of buildsense load s3 store latency/time.",
    labelnames=PrometheusAwsMetricsAdapter.add_labels(),
    buckets=_S3_LATENCY_BUCKETS,
)

COMPRESSION_KEY = "compression"


@unique
class WriteMode(Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    DUPLICATES = "duplicates"


@dataclass
class BuildFile:
    name: str
    content_type: str
    content: bytes
    metadata: FileMetadata
    s3_bucket: str
    s3_key: str

    @property
    def size(self) -> int:
        return len(self.content)


class RunInfoRawStore:
    _MAX_DUPLICATES = 10
    _MAX_BUILD_FILES_DELETION = 45  # based on GoalArtifactsExtractor.MAX_FILE with some buffer for additional files.

    @classmethod
    def for_repo(cls, repo) -> RunInfoRawStore:
        return cls(customer_id=repo.customer_id, repo_id=repo.pk)

    @classmethod
    def for_run_info(cls, run_info) -> RunInfoRawStore:
        return cls(customer_id=run_info.customer_id, repo_id=run_info.repo_id)

    def __init__(self, *, customer_id: str, repo_id: str) -> None:
        self._bucket = settings.BUILDSENSE_BUCKET
        self._base_path = settings.BUILDSENSE_STORAGE_BASE_S3_PATH
        self._customer_id = customer_id
        self._repo_id = repo_id

    def __str__(self) -> str:
        return f"RunInfoRawStore(bucket={self._bucket} path={self._base_path} customer_id={self._customer_id} repo_id={self._repo_id})"

    def _create_key(self, *parts: str) -> str:
        key = os.path.join(self._base_path, self._customer_id, self._repo_id)
        if parts:
            key = os.path.join(key, *parts)
        return key

    @classmethod
    def check_access(cls, repo) -> dict:
        inst = cls(customer_id=repo.customer_id, repo_id=repo.pk)
        return inst._check_read_access()

    def _check_read_access(self) -> dict:
        s3 = S3()
        key = next(s3.keys_with_prefix(bucket=self._bucket, key_prefix=self._create_key()), None)  # type: ignore
        if not key:
            return {"dummy_key": 0}
        data = s3.get_content(bucket=self._bucket, key=key)
        return {key: len(data)}

    def save_initial_build_stats(self, run_id: str, build_stats: dict, user_api_id: str) -> tuple[str, str]:
        return self._save_build_stats_for_stage(
            run_id=run_id,
            build_stats=build_stats,
            stage="start",
            user_api_id=user_api_id,
            ignore_dups=False,
            dry_run=False,
            build_stats_compressed_file=None,
        )

    def save_final_build_stats(
        self,
        run_id: str,
        build_stats: dict,
        user_api_id: str,
        ignore_dups: bool = False,
        dry_run: bool = False,
        build_stats_compressed_file: IO[bytes] | None = None,
    ) -> tuple[str, str]:
        return self._save_build_stats_for_stage(
            run_id=run_id,
            build_stats=build_stats,
            stage="final",
            user_api_id=user_api_id,
            ignore_dups=ignore_dups,
            dry_run=dry_run,
            build_stats_compressed_file=build_stats_compressed_file,
        )

    def _save_build_stats_for_stage(
        self,
        *,
        run_id: str,
        build_stats: dict,
        stage: str,
        user_api_id: str,
        ignore_dups: bool,
        dry_run: bool,
        build_stats_compressed_file: IO[bytes] | None,
    ) -> tuple[str, str]:
        mode = WriteMode.SKIP if ignore_dups else WriteMode.DUPLICATES
        is_compressed = build_stats_compressed_file is not None
        if is_compressed:
            json_bytes_or_file = build_stats_compressed_file
        else:
            json_bytes_or_file = json.dumps(build_stats).encode()  # type: ignore[assignment]
        return self.save_build_json_file(
            run_id=run_id,
            json_bytes_or_file=json_bytes_or_file,  # type: ignore[arg-type]
            name=stage,
            user_api_id=user_api_id,
            mode=mode,
            dry_run=dry_run,
            is_compressed=is_compressed,
        )

    def save_build_json_file(
        self,
        *,
        run_id: str,
        json_bytes_or_file: ContentOrFile,
        name: str,
        user_api_id: str,
        mode: WriteMode,
        dry_run: bool,
        is_compressed: bool,
        metadata: FileMetadata | None = None,
    ) -> tuple[str, str]:
        return self.save_build_file(
            run_id=run_id,
            content_or_file=json_bytes_or_file,
            content_type="application/json",
            name=f"{name}.json",
            user_api_id=user_api_id,
            mode=mode,
            dry_run=dry_run,
            is_compressed=is_compressed,
            metadata=metadata,
        )

    def save_artifact(
        self,
        *,
        run_id: str,
        user_api_id: str,
        content_type: str,
        name: str,
        metadata: FileMetadata | None,
        fp: IO[bytes],
        is_compressed: bool,
    ) -> tuple[str, str]:
        return self.save_build_file(
            run_id=run_id,
            content_or_file=fp,
            content_type=content_type,
            name=name,
            user_api_id=user_api_id,
            mode=WriteMode.SKIP,  # For now we don't allow overwriting of artifact files.
            dry_run=False,
            metadata=metadata,
            is_compressed=is_compressed,
        )

    def _find_key_for_build_file(
        self, *, s3: S3, user_api_id: str, run_id: str, name: str, mode: WriteMode
    ) -> tuple[str, bool]:
        key = self._create_key(user_api_id, run_id, name)
        key_exists = s3.exists(bucket=self._bucket, key=key)
        if not key_exists:
            return key, True
        if mode == WriteMode.SKIP:
            _logger.info(f"save_build_file already exists {key=}")
            return key, False
        if mode == WriteMode.DUPLICATES:
            key = self._find_duplicate_key_name(
                s3_client=s3, key=key, name=name, run_id=run_id, user_api_id=user_api_id
            )
        elif mode == WriteMode.OVERWRITE:
            _logger.info(f"save_build_file Overwrite data in {key}")
        else:
            raise ToolchainAssertion(f"Invalid WriteMode: {mode}")
        return key, True

    def _prepare_data(
        self,
        content_or_file: ContentOrFile,
        metadata: FileMetadata,
        is_compressed: bool,
    ) -> tuple[IO[bytes], int, FileMetadata]:
        final_metadata = {COMPRESSION_KEY: "zlib"} if is_compressed else {}
        final_metadata.update(metadata)
        # TODO: In the future we may want to store the compressed data in s3
        # But we would want to have something in the metadata to indicate compression
        if hasattr(content_or_file, "read"):
            # Leverging logic in Django's file class do determine the size.
            size = content_or_file.size if hasattr(content_or_file, "size") else File(content_or_file).size  # type: ignore[union-attr]
            fp = content_or_file
        elif isinstance(content_or_file, bytes):
            fp = BytesIO(content_or_file)
            size = len(content_or_file)
        else:
            raise ToolchainAssertion(f"Unknown content object type {type(content_or_file)}")
        return fp, size, final_metadata  # type: ignore[return-value]

    @contextmanager
    def _with_client(self, histogram: Histogram) -> Iterator[S3]:
        s3_client = S3()
        with PrometheusAwsMetricsAdapter.track_latency(s3_client, histogram):
            yield s3_client

    def save_build_file(
        self,
        *,
        run_id: str,
        content_or_file: ContentOrFile,
        content_type: str,
        name: str,
        user_api_id: str,
        mode: WriteMode,
        dry_run: bool,
        metadata: FileMetadata | None = None,
        is_compressed: bool = False,
    ) -> tuple[str, str]:
        if not user_api_id:
            raise ToolchainAssertion("User API ID cannot be empty")
        with self._with_client(BUILD_INFO_STORE_LATENCY) as s3_client:
            key, ok = self._find_key_for_build_file(
                s3=s3_client, user_api_id=user_api_id, run_id=run_id, name=name, mode=mode
            )
            if not ok:
                return self._bucket, key
            fp, size, final_metadata = self._prepare_data(content_or_file, metadata or {}, is_compressed)
            _logger.info(f"save_build_file {name=} {content_type=} {size=} {key=} {final_metadata=} {dry_run=}")
            if not dry_run:
                s3_client.upload_fileobj(
                    bucket=self._bucket,
                    key=key,
                    fp=fp,
                    content_type=content_type,
                    metadata=final_metadata,
                )
        return self._bucket, key

    def _find_duplicate_key_name(self, s3_client: S3, key: str, name: str, run_id: str, user_api_id: str) -> str:
        counter = 0
        while counter < self._MAX_DUPLICATES:
            counter += 1
            new_key = self._create_key(user_api_id, run_id, "duplicates", f"{name}_{counter}.json")
            _logger.warning(f"key {key} already exists, uploading to duplicates key. trying {new_key}")
            key = new_key
            if not s3_client.exists(bucket=self._bucket, key=key):
                return key
        raise ToolchainAssertion("Could not find unique key, aborting")

    def get_work_units_artifacts(self, run_info: RunInfo) -> BuildFile | None:
        return self.get_named_data(run_info, name=WU_ARTIFACTS_FILE_NAME)

    def get_platform_info(self, run_info: RunInfo) -> BuildFile | None:
        return self.get_named_data(run_info, name=f"{PLATFORM_INFO_FILE_NAME}.json")

    def _get_key(self, run_info: RunInfo, name: str | None = None) -> PurePath:
        s3_key = run_info.server_info.s3_key
        if run_info.server_info.s3_bucket != self._bucket or not s3_key.startswith(self._base_path):
            raise ToolchainAssertion(
                f"Mismatch in s3 Bucket/Key. Expected bucket={self._bucket} key={self._base_path}/* Got bucket={run_info.server_info.s3_bucket} key={s3_key}"
            )
        path = PurePath(s3_key)
        if name:
            path = path.parent / name
        return path

    def named_data_exists(self, run_info: RunInfo, name: str) -> bool:
        s3 = S3()
        s3_key = self._get_key(run_info, name).as_posix()
        return s3.exists(bucket=self._bucket, key=s3_key)

    def _get_build_file(self, run_info: RunInfo, name: str | None, optional: bool) -> BuildFile | None:
        s3_key_path = self._get_key(run_info, name)
        s3_key = s3_key_path.as_posix()
        if not S3().exists(bucket=self._bucket, key=s3_key_path.as_posix()):
            if optional:
                return None
            raise ToolchainAssertion(f"Missing build file for: run_id={run_info.run_id} at {s3_key=}")
        with self._with_client(BUILD_INFO_LOAD_LATENCY) as s3:
            content, key_info = s3.get_content_with_object(self._bucket, key=s3_key)
        content_type = key_info.content_type
        if not content_type:
            _logger.warning(f"missing_content_type {name=} {s3_key=}")
            content_type = (
                "application/json"  # We may have some old files w/o content type, so we assume those are json files.
            )
        metadata = key_info.metadata or {}
        compression = metadata.get(COMPRESSION_KEY)
        if compression == "zlib":
            content = decompress("get_build_file", content)
        elif compression:
            raise ToolchainAssertion(f"Unknown compression: {compression} {metadata} {s3_key=}")
        bf = BuildFile(
            name=s3_key_path.name,
            content=content,
            content_type=content_type,
            s3_bucket=self._bucket,
            s3_key=s3_key,
            metadata=metadata,
        )
        _logger.info(f"get_build_file {bf.name} run_id={run_info.run_id} size={bf.size} {compression=}")
        return bf

    def get_named_data(self, run_info: RunInfo, name: str, optional: bool = True) -> BuildFile | None:
        build_file = self._get_build_file(run_info, name, optional)
        return build_file

    def delete_named_data(self, run_info: RunInfo, name: str) -> None:
        s3 = S3()
        s3_key = self._get_key(run_info, name).as_posix()
        _logger.info(f"delete_named_data {name=} run_id={run_info.run_id} {s3_key=}")
        s3.delete_object(bucket=self._bucket, key=s3_key)

    def get_build_data(self, run_info: RunInfo) -> dict:
        build_file = self._get_build_file(run_info, name=None, optional=False)
        return json.loads(build_file.content)  # type: ignore[union-attr]

    def delete_build_data(self, *, run_info: RunInfo, dry_run: bool) -> int:
        s3 = S3()
        s3_key = self._get_key(run_info)
        if s3_key.name.startswith("pants_run") and s3.exists(bucket=self._bucket, key=s3_key.as_posix()):
            # Legacy key
            _logger.info(f"delete_build_data [legacy] run_id={run_info.run_id} s3_key={s3_key.as_posix()} {dry_run=}")
            if not dry_run:
                s3.delete_object(bucket=self._bucket, key=s3_key.as_posix())
            return 1
        s3_key_base = s3_key.parent
        if not s3_key_base.name.startswith("pants_run"):
            raise ToolchainAssertion(f"Unexpected s3 key in delete_build_data {s3_key.as_posix()}")
        keys = list(s3.keys_with_prefix(bucket=self._bucket, key_prefix=s3_key_base.as_posix()))
        if len(keys) > self._MAX_BUILD_FILES_DELETION:
            # Protect against bugs that will delete too much data.
            raise ToolchainAssertion(
                f"Unexpected number of keys under {s3_key_base.as_posix()} objects_count={len(keys)}"
            )
        _logger.info(
            f"delete_build_data run_id={run_info.run_id} s3_key={s3_key_base.as_posix()} objects_count={len(keys)} {dry_run=}"
        )
        if not dry_run:
            s3.delete_objects_with_key_prefix(bucket=self._bucket, key_prefix=s3_key_base.as_posix())
        return len(keys)

    def list_files(self, run_info: RunInfo) -> tuple[str, ...]:
        s3 = S3()
        s3_path = self._get_key(run_info).parent
        keys = s3.keys_with_prefix(bucket=self._bucket, key_prefix=s3_path.as_posix())
        return tuple(keys)
