# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict

from toolchain.buildsense.ingestion.run_processors.common import (
    BaseHandler,
    ExtractedArtifacts,
    FileInfo,
    WorkUnitWithArtifacts,
)

_logger = logging.getLogger(__name__)


class ConsoleArtifactsHandler(BaseHandler):
    _CONTENT_TYPE = "text/plain"
    types = ("stdout", "stderr")
    _GROUP_ARTIFACTS_FOR_GOALS = frozenset(["test", "lint", "fmt", "check", "update-build-files", "package"])
    _EMPTY_ARTIFACTS = frozenset(
        [
            "[]",
        ]
    )

    def __init__(self) -> None:
        self._files: list[FileInfo] = []
        self._artifacts: dict[str, list[dict]] = defaultdict(list)
        self._metadata: dict[str, tuple[str, dict, dict]] = {}
        self._goals_to_workunits: dict[str, list[dict]] = defaultdict(list)
        self._start_time_usec = 0  # Will be initilized by init_processing

    def _get_result(self, work_unit: dict) -> str | None:
        exit_code = work_unit.get("metadata", {}).get("exit_code")
        if exit_code is None:
            return None
        # Using the same values as in RunInfo.outcome
        return "SUCCESS" if exit_code == 0 else "FAILURE"

    def init_processing(self, start_time_usec: int) -> None:
        self._start_time_usec = start_time_usec

    def handle_work_unit_artifacts(self, artifacts_wu: WorkUnitWithArtifacts, goal: str) -> bool:
        handle_count = 0
        for name, artifact in artifacts_wu.artifacts.items():
            handled = self.handle_artifact(
                goal=goal,
                significant_work_unit=artifacts_wu.significant_work_unit,
                artifact_work_unit=artifacts_wu.work_unit,
                name=name,
                artifact=artifact,
            )
            if handled:
                handle_count += 1

        return handle_count > 0

    def handle_artifact(
        self, goal: str, significant_work_unit: dict, artifact_work_unit: dict, name: str, artifact: str
    ) -> bool:
        if name not in self.types:
            return False
        if artifact.strip() in self._EMPTY_ARTIFACTS:
            return True
        workunit_id = artifact_work_unit["workunit_id"]
        group = significant_work_unit["name"] if goal in self._GROUP_ARTIFACTS_FOR_GOALS else workunit_id
        self._get_timing_data(artifact_work_unit)
        env_info = self._get_env_info(artifact_work_unit, workunit_id=workunit_id)
        group_info: dict[str, str | bool | dict[str, int]] = {
            "name": name,
            "content_type": self._CONTENT_TYPE,
            "content": artifact,
            "timing_msec": self._get_timing_data(artifact_work_unit),
        }
        if env_info:
            group_info.update(env_info)
        self._artifacts[group].append(group_info)
        self._metadata[group] = (goal, significant_work_unit, artifact_work_unit)
        return True

    def _get_env_info(self, artifact_work_unit, workunit_id: str) -> dict[str, str | bool] | None:
        metadata = artifact_work_unit.get("metadata", {})
        source = metadata.get("source")
        env_type = metadata.get("environment_type")  # only in Pants 2.16 and later
        if source in ("Ran", "RanLocally", "RanRemotely"):
            from_cache = False
        elif source in ("HitLocally", "HitRemotely"):
            from_cache = True
        else:
            _logger.warning(f"Can't determine exec info source for {workunit_id=} {source=} {env_type=}")
            return None
        if env_type == "local":
            env_name = "Local"
        elif env_type == "remote":
            env_name = "Remote"
        elif source in ("RanLocally", "HitLocally") and not env_type:
            env_name = "Local"
        else:
            _logger.info(f"unknown_env_type: {workunit_id=} {source=} {env_type=} {metadata.get('environment_name')}")
            env_name = env_type or "unknown"
        return {"env_name": env_name, "from_cache": from_cache}

    def _get_timing_data(self, artifacts_wu: dict) -> dict[str, int]:
        start_usecs = artifacts_wu["start_usecs"]
        run_time_msec = int((artifacts_wu["end_usecs"] - start_usecs) / 1000)
        relative_start_time_msec = int((start_usecs - self._start_time_usec) / 1000)
        return {
            "start_time": relative_start_time_msec,
            "run_time": run_time_msec,
        }

    def _process(self) -> tuple[dict[str, list[dict]], list[FileInfo]]:
        goals_to_workunits: dict[str, list[dict]] = defaultdict(list)
        files: list[FileInfo] = []
        for group, artifacts_data in self._artifacts.items():
            goal, significant_work_unit, artifacts_wu = self._metadata[group]
            artifacts_file = FileInfo.create_json_file(
                f"{goal}_{artifacts_wu['workunit_id']}_artifacts", artifacts_data
            )
            files.append(artifacts_file)
            description = significant_work_unit.get("description")
            name = significant_work_unit["name"]
            if not description:
                description = name.split(".")[-1] if "." in name else name
            artifacts_dict = {
                "work_unit_id": significant_work_unit["workunit_id"],
                "name": name,
                "description": description,
                "artifacts": artifacts_file.name,
                "content_types": [self._CONTENT_TYPE],
                "priority": 5,
            }
            result = self._get_result(artifacts_wu)
            if result:
                artifacts_dict["result"] = result
            goals_to_workunits[goal].append(artifacts_dict)
        return goals_to_workunits, files

    def get_artifacts(self) -> ExtractedArtifacts:
        goals_to_workunits, files = self._process()
        return ExtractedArtifacts(files=files, work_units_by_goal=goals_to_workunits)
