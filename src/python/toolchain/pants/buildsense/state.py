# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import queue
import time
from enum import Enum, unique
from pathlib import Path
from typing import Tuple

from pants.engine.fs import Snapshot

from toolchain.base.datetime_tools import utcnow
from toolchain.pants.buildsense.client import BuildSenseClient
from toolchain.pants.buildsense.common import Artifacts, RunTrackerBuildInfo, WorkUnitsMap
from toolchain.pants.buildsense.converter import WorkUnitConverter
from toolchain.pants.buildsense.local_store import LocalBuildsStore
from toolchain.pants.common.errors import ToolchainPluginError

logger = logging.getLogger(__name__)
WorkUnitsChunk = Tuple[int, WorkUnitsMap, int]


class InvalidStateError(ToolchainPluginError):
    """Raised when there is an invalid state in the reporter logic."""


@unique
class ReportOperation(Enum):
    NO_OP = "no_op"
    SENT = "sent"
    ERROR = "error"

    def is_sent(self) -> bool:
        return self == self.SENT

    def is_error(self) -> bool:
        return self == self.ERROR


class BuildState:
    _PANTS_LOG_ARTIFACT_NAME = "pants_run_log"

    def __init__(
        self,
        client: BuildSenseClient,
        local_store_base_path: Path,
        max_batch_size_mb: int,
        local_store_enabled: bool,
        snapshot_type: type = Snapshot,
        log_final_upload_latency: bool = True,
    ):
        self._enabled = True
        self._client = client
        self._initial_report: RunTrackerBuildInfo | None = None
        self._end_report_data: tuple[RunTrackerBuildInfo, int] | None = None
        self._sent_initial_report = False
        self._run_id: str | None = None
        self._ci_user_api_id: str | None = None
        self._workunits_chunks_queue: queue.LifoQueue = queue.LifoQueue(maxsize=300)
        self._snapshot_type = snapshot_type
        self.__converter: WorkUnitConverter | None = None
        self._pants_context = None
        self._local_store = LocalBuildsStore(
            base_path=local_store_base_path, max_batch_size_mb=max_batch_size_mb, enabled=local_store_enabled
        )
        self._sumbit_batches = True
        self._build_link: str | None = None
        self._config: dict | None = None
        self._asked_for_config = False
        self._log_final_upload_latency = log_final_upload_latency

    @property
    def build_link(self) -> str | None:
        return self._build_link

    @property
    def ci_capture_config(self) -> dict[str, str] | None:
        return self._config["ci_capture"] if self._config else None

    def set_context(self, context) -> None:
        self._pants_context = context

    def _get_converter(self) -> WorkUnitConverter:
        converter = self.__converter
        if not converter:
            converter = (
                WorkUnitConverter.from_server(self._config, self._snapshot_type)
                if self._config
                else WorkUnitConverter.create_local(self._snapshot_type)
            )
        if self._pants_context:
            converter.set_context(self._pants_context)
        self.__converter = converter
        return converter

    def queue_workunits(self, call_num: int, workunits: WorkUnitsMap, timestamp: int | None = None) -> None:
        if not self._enabled:
            # Don't queue up work units when buildsense is disabled, wastes memory.
            return
        timestamp = timestamp or int(utcnow().timestamp())
        run_id = self._run_id
        if not workunits:
            return
        if not run_id:
            raise InvalidStateError("run_id must be initialized.")
        self._workunits_chunks_queue.put_nowait((call_num, workunits, timestamp))

    def set_run_id(self, run_tracker_info: RunTrackerBuildInfo) -> None:
        self._run_id = run_tracker_info.run_id

    def queue_initial_report(self, run_tracker_info: RunTrackerBuildInfo) -> None:
        self.set_run_id(run_tracker_info)
        self._initial_report = run_tracker_info

    def build_ended(self, run_tracker_info: RunTrackerBuildInfo, call_count: int, work_units_map: WorkUnitsMap) -> None:
        self.set_run_id(run_tracker_info)
        self.queue_workunits(call_count, work_units_map)
        self.submit_final_report(run_tracker_info, call_count)

    def submit_final_report(self, run_tracker_info: RunTrackerBuildInfo, calls_count: int) -> None:
        if not run_tracker_info.has_ended:
            logger.warning("RunTracker.end() was not called")
            return
        self._run_id = self._run_id or run_tracker_info.run_id
        logger.debug(
            f"submit_final_report run_id={self._run_id} calls={calls_count} keys={run_tracker_info.build_stats.keys()}"
        )
        self._end_report_data = run_tracker_info, calls_count

    def send_report(self) -> ReportOperation:
        # Expects to be non-reentrant
        if not self._enabled:
            return ReportOperation.ERROR
        if not self._client.is_auth_available():
            logger.warning("Auth failed - BuildSense plugin is disabled.")
            self._enabled = False
            return ReportOperation.ERROR
        self._maybe_get_config()
        operation = self._maybe_send_initial_report()
        if operation.is_error():
            return operation
        sent = self._send_workunit_queue()
        if sent:
            return ReportOperation.SENT
        batch_sent = self._maybe_send_batched_builds()
        return ReportOperation.SENT if batch_sent or operation.is_sent() else ReportOperation.NO_OP

    def _get_log_file(self, run_tracker_info: RunTrackerBuildInfo) -> bytes | None:
        if not run_tracker_info.log_file:
            logger.warning("no log file associated in run tracker")
            return None
        log_data = run_tracker_info.log_file.read_bytes()
        logger.debug(f"get_log_file log_file={run_tracker_info.log_file.as_posix()} size={len(log_data)}")
        return log_data

    def _get_artifacts(self, converter: WorkUnitConverter, run_tracker_info: RunTrackerBuildInfo) -> Artifacts:
        artifacts = converter.get_standalone_artifacts() or {}
        pants_run_log = self._get_log_file(run_tracker_info)
        if pants_run_log:
            artifacts[self._PANTS_LOG_ARTIFACT_NAME] = pants_run_log
        return artifacts

    def send_final_report(self) -> None:
        if self._end_report_data is None:
            raise InvalidStateError("End report data not captured.")
        start = time.time()
        run_tracker_info, calls_count = self._end_report_data
        build_stats = run_tracker_info.build_stats
        # Make sure we don't miss any work units we didn't de-queue yet
        call_num, workunits, timestamp = self._get_lastest_workunits()
        converter = self._get_converter()
        converter.transform(workunits, call_num, timestamp)
        all_workunits = converter.get_all_work_units(call_num=calls_count, last_update_timestamp=int(time.time()))
        build_stats["workunits"] = all_workunits
        run_id = self._run_id
        if not run_id:
            logger.warning("run_id is missing")
            return
        if not build_stats:
            logger.warning("final build report missing")
            return
        artifacts = self._get_artifacts(converter, run_tracker_info)
        logger.debug(f"send_final_report workunits={len(all_workunits)} artifacts={len(artifacts)}")
        run_end_info = self._client.submit_run_end(
            run_id=run_id, user_api_id=self._ci_user_api_id, build_stats=build_stats
        )
        if run_end_info.success:
            self._build_link = self._build_link or run_end_info.build_link
        else:
            # If submission failed, submit_run_end returns the data so we can store it for later upload
            self._local_store.store_build(run_id=run_id, json_build_data=run_end_info.data)
            return
        self._maybe_upload_artifacts(run_id, artifacts)
        latency = time.time() - start
        if self._log_final_upload_latency:
            logger.info(f"BuildSense final upload took {latency:.3f} seconds.")

    def _maybe_upload_artifacts(self, run_id: str, artifacts: Artifacts) -> None:
        if not artifacts:
            return
        self._client.upload_artifacts(run_id=run_id, artifacts=artifacts, user_api_id=self._ci_user_api_id)
        # TODO: Store artifacts for later in self._local_store if upload fails.

    def _maybe_get_config(self) -> None:
        if self._asked_for_config:
            return
        self._asked_for_config = True
        config_response = self._client.get_plugin_config()
        if config_response:
            self._config = config_response["config"]
        logger.debug(f"Got config from server: {(self._config or {}).keys()}")

    def _maybe_send_initial_report(self) -> ReportOperation:
        if self._sent_initial_report:
            return ReportOperation.NO_OP
        run_tracker_info = self._initial_report
        if self._sent_initial_report or not run_tracker_info:
            return ReportOperation.NO_OP
        run_info = self._client.submit_run_start(
            run_id=run_tracker_info.run_id, build_stats=dict(run_tracker_info.build_stats)
        )
        if not run_info:
            return ReportOperation.ERROR
        self._ci_user_api_id = run_info.ci_user_api_id
        self._sent_initial_report = True
        self._build_link = run_info.build_link
        return ReportOperation.SENT

    def _send_workunit_queue(self) -> bool:
        call_num, workunits, timestamp = self._get_lastest_workunits()
        if not workunits:
            return False
        logger.debug(f"send_workunit_queue workunits={len(workunits)} call={call_num}")
        run_id = self._run_id
        if not run_id:
            raise InvalidStateError("run_id must be initialized.")
        converter = self._get_converter()
        buildsense_workunits = converter.transform(workunits, call_num, timestamp)
        if not buildsense_workunits:
            return False
        self._client.submit_workunits(
            run_id=run_id, call_num=call_num, user_api_id=self._ci_user_api_id, workunits=buildsense_workunits
        )
        return True

    def _maybe_send_batched_builds(self) -> bool:
        if not self._client.has_successful_calls and self._sumbit_batches:
            return False
        batched_build = self._local_store.get_upload_batch()
        if not batched_build:
            return False
        success = self._client.submit_batch(
            batched_data=batched_build.get_batched_data(),
            batch_name=batched_build.name,
            user_api_id=self._ci_user_api_id,
        )
        if success:
            self._local_store.delete_batch_file(batched_build)
        else:
            # If we failed, don't try again during this run
            self._sumbit_batches = False
        return True

    def _empty_queue(self) -> list[WorkUnitsChunk]:
        data = []
        while self._workunits_chunks_queue.not_empty:
            try:
                data.append(self._workunits_chunks_queue.get_nowait())
            except queue.Empty:
                break
        return data

    def _get_lastest_workunits(self) -> WorkUnitsChunk:
        data = self._empty_queue()
        if not data:
            return -1, dict(), 0
        workunits_dict: WorkUnitsMap = {}
        # Ensures that we handle the latest chunks first (based on the call_num)
        # Protects against a race in which data is queued while we try to empty the queue.
        data = sorted(data, reverse=True, key=lambda x: x[0])
        for _, wu_chunk, _ in data:
            for wu_id, workunit in wu_chunk.items():
                workunits_dict.setdefault(wu_id, workunit)
        last_chunk = data[0]
        last_call_num = last_chunk[0]
        timestamp = last_chunk[2]
        return last_call_num, workunits_dict, timestamp
