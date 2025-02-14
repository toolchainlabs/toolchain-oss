# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass, fields

from toolchain.base.memo import memoized_method
from toolchain.buildsense.ingestion.run_processors.common import FileInfo
from toolchain.buildsense.records.run_info import RunInfo

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkUnit:
    name: str
    start_usecs: int
    end_usecs: int
    workunit_id: str
    last_update: int
    parent_ids: list[str] | None = None
    description: str | None = None

    @classmethod
    @memoized_method
    def _get_field_names(cls) -> set[str]:
        return {*(field.name for field in fields(cls)), "parent_id"}

    @classmethod
    def from_json(cls, json_data: dict) -> WorkUnit:
        fields = cls._get_field_names()
        cleaned_json = {key: value for key, value in json_data.items() if key in fields}
        parent_id = cleaned_json.pop("parent_id", None)
        if parent_id:
            cleaned_json["parent_ids"] = [parent_id]
        return cls(**cleaned_json)


def _fix_data(wu_json: dict) -> None:
    if "end_usecs" not in wu_json:
        wu_json["end_usecs"] = wu_json["start_usecs"]


def create_zipkin_trace(run_id: str, work_units_json: list[dict]) -> list[dict]:
    spans: list[dict] = []
    for wu_json in work_units_json:
        _fix_data(wu_json)
        wu = WorkUnit.from_json(wu_json)
        span = {
            "traceId": run_id,
            "name": wu.description,
            "id": wu.workunit_id,
            "timestamp": wu.start_usecs,
            "duration": wu.end_usecs - wu.start_usecs,
            "localEndpoint": {"serviceName": wu.name},
        }
        if wu.parent_ids:
            # NB: Zipkin does not support multiple parents in traces, but Jaeger does.
            span["parentId"] = wu.parent_ids[0]
        spans.append(span)
    return spans


def create_zipkin_trace_files(run_info: RunInfo, build_data: dict) -> FileInfo | None:
    if run_info.server_info.stats_version != "3":
        return None
    work_units = build_data.get("workunits")
    if not work_units:
        _logger.warning(f"Missing work units from run_id={run_info.run_id} keys={build_data.keys()}")
        return None
    zipkin_trace_json = create_zipkin_trace(run_id=run_info.run_id, work_units_json=work_units)
    file_info = FileInfo.create_json_file("zipkin_trace", zipkin_trace_json, compress=True)
    _logger.info(
        f"created_zipkin_trace for run_id={run_info.run_id} steps={len(zipkin_trace_json)} size={file_info.size:,}"
    )
    return file_info
