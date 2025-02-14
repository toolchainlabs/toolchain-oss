# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from pants.util.dirutil import safe_concurrent_creation

from toolchain.base.datetime_tools import utcnow
from toolchain.pants.buildsense.common import Artifacts

_logger = logging.getLogger(__name__)


@dataclass
class BatchedData:
    path: Path
    version: str
    num_of_files: int

    def get_metadata(self) -> dict:
        return {"version": self.version, "num_of_files": self.num_of_files}

    @property
    def name(self) -> str:
        return self.path.name

    def get_batched_data(self) -> str:
        return self.path.read_text()


class LocalBuildsStore:
    _TIMESTAMP_FMT = "%Y_%m_%d_%H_%M_%S"
    BATCH_VERSION = "1"

    def __init__(self, base_path: Path, max_batch_size_mb: int, enabled: bool) -> None:
        self._enabled = enabled
        self._build_queue = base_path / "queue"
        self._upload_staging = base_path / "upload"
        self._build_queue.mkdir(parents=True, exist_ok=True)
        self._upload_staging.mkdir(parents=True, exist_ok=True)
        self._max_batch_size = 1024 * 1024 * max_batch_size_mb  # keep it in bytes

    def store_build(self, run_id: str, json_build_data: str) -> None:
        if not self._enabled:
            return
        _logger.debug(f"store_build run_id={run_id} data={len(json_build_data)}")
        self._queue_data(run_id, "build_stats", json_build_data)

    def store_artifacts(self, run_id: str, artifacts: Artifacts) -> None:
        if not self._enabled:
            return
        _logger.debug(f"store_artifacts run_id={run_id} data={len(artifacts)}")
        encoded_artifacts = {name: base64.encodebytes(data).decode() for name, data in artifacts.items()}
        data = {
            "run_id": run_id,
            "artifacts": encoded_artifacts,
        }
        self._queue_data(run_id, "artifacts", json.dumps(data))

    def _queue_data(self, run_id: str, data_type: str, json_data: str) -> None:
        fn = self._build_queue / data_type / f"{run_id}.json"
        with safe_concurrent_creation(fn.as_posix()) as tmp_filename, open(tmp_filename, "w") as fl:
            fl.write(json_data)

    def get_upload_batch(self) -> BatchedData | None:
        if not self._enabled:
            return None
        upload_batch = next(self._upload_staging.iterdir(), None)
        if upload_batch:
            num_of_files = self._get_num_of_files(upload_batch)
            return BatchedData(path=upload_batch, version=self.BATCH_VERSION, num_of_files=num_of_files)
        return self._create_batch()

    def _get_num_of_files(self, batch_file: Path) -> int:
        num_of_files = 0
        for files in json.loads(batch_file.read_bytes()).values():
            if isinstance(files, dict):
                num_of_files += len(files)
        return num_of_files

    def _create_batch(self) -> BatchedData | None:
        timestamp = utcnow().strftime(self._TIMESTAMP_FMT)
        batch, files_in_batch = self._get_batched_data()
        if not files_in_batch:
            return None

        batch_file = self._upload_staging / f"{timestamp}_{os.getpid()}.json"
        with safe_concurrent_creation(batch_file.as_posix()) as tmp_filename, open(tmp_filename, "w") as fl:
            fl.write(batch)
        for build_file in files_in_batch:
            build_file.unlink()
        return BatchedData(path=batch_file, version=self.BATCH_VERSION, num_of_files=len(files_in_batch))

    def _get_batched_data(self) -> tuple[str, list[Path]]:
        files_in_batch = []
        batch_data = {"version": self.BATCH_VERSION}
        # Doing some work to account for existing files, will remove after everyone runs this version of the plugin
        for sub_dir, key in [("", "build_stats"), ("build_stats", "build_stats")]:
            files_batch = self._get_files_for_batch(sub_dir)
            if not files_batch:
                continue
            files_in_batch.extend(files_batch)
            batch_data[key] = {build_file.stem: json.loads(build_file.read_bytes()) for build_file in files_batch}  # type: ignore[assignment]
        return json.dumps(batch_data), files_in_batch

    def delete_batch_file(self, batch_data: BatchedData) -> None:
        batch_file = batch_data.path
        if batch_file.exists():
            batch_file.unlink()

    def _get_files_for_batch(self, sub_dir: str) -> list[Path]:
        # Latest builds first.
        def sort_key(fl: Path) -> tuple[int, str]:
            last_modification = int(fl.stat().st_mtime / 60)  # Reduce accuracy. mostly to prevent flaky tests
            return last_modification, fl.stem

        queue_dir = self._build_queue
        if sub_dir:
            queue_dir = queue_dir / sub_dir
        if not queue_dir.exists():
            return []
        build_files = sorted(queue_dir.iterdir(), key=sort_key, reverse=True)
        files_to_upload = []
        total_size = 0
        for build_file in build_files:
            if not build_file.is_file():
                continue
            size = build_file.stat().st_size
            if size + total_size > self._max_batch_size:
                break
            total_size += size
            files_to_upload.append(build_file)
        return files_to_upload
