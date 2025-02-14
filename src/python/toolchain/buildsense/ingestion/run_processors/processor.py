# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from pathlib import PurePath

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.integrations.ci_integration import get_ci_info
from toolchain.buildsense.ingestion.integrations.ci_scm_helpers import update_ci_scm_data
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_processors.artifacts import GoalArtifactsExtractor
from toolchain.buildsense.ingestion.run_processors.common import (
    RUN_LOGS_ARTIFACTS_FILE_NAME,
    FileInfo,
    PipelineResults,
    ProcessRunResults,
    StandaloneArtifact,
)
from toolchain.buildsense.ingestion.run_processors.indicators_builder import calculate_indicators
from toolchain.buildsense.ingestion.run_processors.zipkin_trace import create_zipkin_trace_files
from toolchain.buildsense.records.run_info import RunInfo, ScmProvider

_logger = logging.getLogger(__name__)


def process_pants_run(run_info: RunInfo, scm: ScmProvider) -> ProcessRunResults:
    processor = ProcessPantsData(run_info, scm)
    return processor.process_run()


class ArtifactFilesHelper:
    def __init__(self, run_info: RunInfo) -> None:
        self._info_store = RunInfoRawStore.for_run_info(run_info)
        self._run_info = run_info

    def get_existing_files(self) -> set[str]:
        old_artifacts_file = self._info_store.get_work_units_artifacts(self._run_info)
        existing_files: set[str] = set()
        if not old_artifacts_file:
            return existing_files
        existing_files.add(PurePath(old_artifacts_file.s3_key).name)
        work_units = json.loads(old_artifacts_file.content)
        for goal_work_units in work_units.values():
            existing_files.update(wu["artifacts"] for wu in goal_work_units)
        return existing_files

    def get_log_artifact(self) -> str | None:
        if self._info_store.named_data_exists(self._run_info, RUN_LOGS_ARTIFACTS_FILE_NAME):
            return RUN_LOGS_ARTIFACTS_FILE_NAME
        return None

    def get_standalone_artifacts(self, expected_names: frozenset[str]) -> list[StandaloneArtifact]:
        artifacts: list[StandaloneArtifact] = []
        for name in expected_names:
            build_file = self._info_store.get_named_data(self._run_info, name=name, optional=True)
            if not build_file:
                continue
            work_unit_id = build_file.metadata.get("workunit_id")
            if not work_unit_id:
                _logger.warning(f"missing_metadata for s3 file: name={build_file.name} key={build_file.s3_key}")
                continue
            artifacts.append(
                StandaloneArtifact(
                    workunit_id=work_unit_id,
                    name=name,
                    content_type=build_file.content_type,
                    content=build_file.content,
                )
            )
        return artifacts

    def store_result_files(self, files: tuple[FileInfo, ...]) -> None:
        for file_info in files:
            self._info_store.save_build_file(
                run_id=self._run_info.run_id,
                content_or_file=file_info.content,
                content_type=file_info.content_type,
                name=file_info.name,
                user_api_id=self._run_info.user_api_id,
                mode=WriteMode.OVERWRITE,
                dry_run=False,
                is_compressed=file_info.compressed,
            )


class ProcessPantsData:
    def __init__(self, run_info: RunInfo, scm: ScmProvider) -> None:
        self._run_info = run_info
        self._scm = scm
        self._info_store = RunInfoRawStore.for_run_info(run_info)
        self._files = ArtifactFilesHelper(run_info)
        self._extractor = GoalArtifactsExtractor.create()

    def process_run(self) -> ProcessRunResults:
        existing_files = self._files.get_existing_files()
        build_data = self._info_store.get_build_data(self._run_info)
        if not build_data:
            raise ToolchainAssertion(f"Couldn't load build data for {self._run_info}")
        log_artifact = self._files.get_log_artifact()
        result = self.pipeline(build_data, log_artifact)
        updated_run_info = result.run_info
        if result.has_metrics:
            indicators = calculate_indicators(self._run_info.run_id, result)
            if indicators:
                updated_run_info.indicators = indicators
        self._files.store_result_files(result.files)
        existing_file_sz = len(existing_files)
        files_to_delete = sorted(existing_files.difference(result.get_names()))
        _logger.info(
            f"Update run info for {updated_run_info.run_id} - run_time={updated_run_info.run_time} files={len(result.files)} existing={existing_file_sz} files_to_delete={len(files_to_delete)}"
        )
        return ProcessRunResults(
            run_info=updated_run_info, files_to_delete=tuple(files_to_delete), has_metrics=result.has_metrics
        )

    def pipeline(self, build_data: dict, log_artifact_name: str | None) -> PipelineResults:
        run_info = self._run_info
        run_time = _extract_run_time(build_data)
        if not run_time:
            _logger.warning(f"Failed to resolve run_time for {run_info.run_id}")
        run_info.run_time = run_time
        all_files = []
        zipkin_file = create_zipkin_trace_files(run_info, build_data)
        if zipkin_file:
            all_files.append(zipkin_file)
        ci_info = run_info.ci_info
        if ci_info:
            ci_full_details = get_ci_info(build_data["ci_env"], context=f"run_id={run_info.run_id}")
            update_ci_scm_data(scm=self._scm, run_info=run_info, ci_full_details=ci_full_details)  # type: ignore[arg-type]
        if run_info.server_info.stats_version == "3":
            standalone_artifacts = self._files.get_standalone_artifacts(
                self._extractor.allowed_standalone_artifact_names
            )
            result = self._extractor.get_artifacts(run_info, build_data, log_artifact_name, standalone_artifacts)
            artifact_files = result.files
            _logger.info(f"extract_artifacts run_id={run_info.run_id} files={len(artifact_files)}")
            all_files.extend(artifact_files)
            has_metrics = result.has_metrics
        else:
            has_metrics = False
        return PipelineResults(run_info=run_info, files=tuple(all_files), has_metrics=has_metrics)


def _extract_run_time(build_data) -> datetime.timedelta | None:
    # should we blow up here or not?
    cumulative_timings = build_data.get("cumulative_timings")
    if not cumulative_timings:
        return None
    run_time_ms = int(cumulative_timings[0]["timing"] * 1000)
    return datetime.timedelta(milliseconds=run_time_ms)
