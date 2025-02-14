# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import json
import zlib
from dataclasses import dataclass
from typing import Optional, Union

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.records.run_info import RunInfo

ArtifactType = Union[str, bytes, dict[str, str]]
WU_ARTIFACTS_FILE_NAME = "artifacts_work_units.json"
RUN_LOGS_ARTIFACTS_FILE_NAME = "pants_run_log.txt"
RUN_LOGS_ARTIFACTS_CONTENT_TYPE = "text/plain"
METRICS_FILE_NAME = "aggregate_metrics"
PLATFORM_INFO_FILE_NAME = "platform_info"


@dataclass
class WorkUnitWithArtifacts:
    work_unit: dict
    significant_work_unit: dict
    artifacts: dict

    @property
    def workunit_id(self) -> str:
        return self.work_unit["workunit_id"]

    @property
    def significant_work_unit_id(self) -> str:
        return self.significant_work_unit["workunit_id"]

    @property
    def metadata(self) -> dict:
        return self.work_unit.get("metadata", {})


@dataclass(frozen=True)
class StandaloneArtifact:
    workunit_id: str
    name: str
    content_type: str
    content: bytes

    def as_artifacts_dict(self) -> dict:
        return {self.name: self.content}


@dataclass(frozen=True, order=True)
class FileInfo:
    name: str
    content_type: str
    content: bytes
    compressed: bool

    @classmethod
    def create_json_file(cls, name: str, json_data: list | dict, compress: bool = False) -> FileInfo:
        content = json.dumps(json_data).encode()
        if compress:
            content = zlib.compress(content)
        return cls(name=f"{name}.json", content_type="application/json", content=content, compressed=compress)

    @property
    def size(self) -> int:
        return len(self.content)


RunArtifact = Optional[tuple[FileInfo, dict[str, Union[str, list[str]]]]]


@dataclass
class ExtractedArtifacts:
    files: list[FileInfo]
    work_units_by_goal: dict[str, list[dict]]


class BaseHandler(abc.ABC):
    types: tuple[str, ...] = tuple()
    standalone_name: str | None = None

    def init_processing(self, start_time_usec: int) -> None:  # noqa: B027
        """Optional method that can be implemented by handlers."""

    @abc.abstractmethod
    def handle_work_unit_artifacts(self, artifacts_wu: WorkUnitWithArtifacts, goal: str) -> bool:
        pass

    @abc.abstractmethod
    def get_artifacts(self) -> ExtractedArtifacts:
        pass


@dataclass
class PipelineResults:
    run_info: RunInfo
    files: tuple[FileInfo, ...]
    has_metrics: bool

    def get_names(self) -> set[str]:
        return {fl.name for fl in self.files}

    def get_json_by_name(self, name: str) -> bytes:
        for fl in self.files:
            if fl.name == f"{name}.json":
                return fl.content
        raise ToolchainAssertion(f"Can't find file {name=}")


@dataclass
class ProcessRunResults:
    run_info: RunInfo
    files_to_delete: tuple[str, ...]
    has_metrics: bool
