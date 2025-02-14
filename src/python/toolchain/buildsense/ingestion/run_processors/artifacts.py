# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass

from sentry_sdk import push_scope

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.run_processors.common import (
    RUN_LOGS_ARTIFACTS_CONTENT_TYPE,
    BaseHandler,
    FileInfo,
    RunArtifact,
    StandaloneArtifact,
    WorkUnitWithArtifacts,
)
from toolchain.buildsense.ingestion.run_processors.console import ConsoleArtifactsHandler
from toolchain.buildsense.ingestion.run_processors.options_extrator import get_pants_options
from toolchain.buildsense.ingestion.run_processors.pants_run_metrics import get_run_metrics
from toolchain.buildsense.ingestion.run_processors.platform_info_extractor import get_platform_info
from toolchain.buildsense.ingestion.run_processors.pytest_junit_xml import PytestJUnitXmlArtifactsHandler
from toolchain.buildsense.ingestion.run_processors.python_coverage_xml import XmlCoverageArtifactsHandler
from toolchain.buildsense.ingestion.run_processors.targets_extractor import get_targets
from toolchain.buildsense.records.run_info import RunInfo

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactsExtractResult:
    files: tuple[FileInfo, ...]
    has_metrics: bool


class MissingParentWorkUnitError(ToolchainAssertion):
    """Raised when a parent work unit is missing."""


def compile_expression(items: tuple[str, ...]) -> re.Pattern:
    return re.compile("|".join(f".*{item}" for item in items))


class GoalArtifactsExtractor:
    _IGNORED_NAMES = (
        # Rule s name to skip/ignore when walking the WU tree up to try and locate a significant parent.
        # for example: we ignore the process execution rule (multi_platform_process) and keep going up the work unit hierarchy in order to find a rule
        # that says something like "lint with black"
        "multi_platform_process[a-z_-]*",
        "process",
        "remove_platform_information",
        "fallible_to_exec_result_or_raise",
        "find_pex_python",
        "create_pex",
        "create_optional_pex",
        "build_pex",
        "_partition",
        "local_cache[a-z_-]*",
        "remote_cache[a-z_-]*",
        r"pants\.engine\.internals\.graph",
        "dockerfile_parser",
    )

    _IGNORE_ARTIFACTS_RULE_NAMES = (
        # artifact from these rules will be ignored since it is not relevant to end users, so when we see one of those rules in the WU hierarchy
        # we just stop looking for significant parent and not include the artifact (stdout/stderr) in the artifacts we expose to the user.
        # For example, pants runs a process to find binaries (tar, zip, etc...) as part of the execution however the process outputs (stdout/stderro) from those
        # are not interesting to an end user and thus we will not expose them.
        "find_binary",
        "find_interpreter",
        "extract_distributions",
        "maybe_extract_archive",
        "create_venv_pex",
        "transitive_targets",
        "pex_from_targets",
        r"\.pex\.build_pex",
        "dependency_inference",
        "project_info.dependencies.dependencies",
        "find_bash",
        "find_docker",
        "pants.backend.scala.goals.check.scalac_check",
        "coursier_fetch",
        "setup_jdk",
        "merge_coverage_data",
        # Golang
        "setup_goroot",
        "determine_go_mod_info",
        "third_party_pkg",
        "import_analysis",
        "analyze_first_party_package",
        r"\.system_binaries\.",
        "create_pex_binary_run_request",
        "find_pex_python",
        r"\.go\.util_rules\.build_pkg",
        "generate_targets_from_go_mod",
        # mypy (python)
        r"\.mypy\.rules\.mypy_determine_partitions",
        # pylint
        "pylint_determine_partitions",
    )

    _IGNORE_ARTIFACTS_RULE_DESCRIPTION = (
        r"Searching for .python.",
        r"Test binary",
        r"Ensure download of JDK",
        r"Fetching with coursier",
        r"Determine Python dependencies",
        r"Parse Dockerfile",
        r"Detect Shell imports",
    )

    _GOALS_ALIASES = {
        # We can make the values here to be tuples if we need to match more than one pattern
        # or we can change the regex to match more patterns.
        "test": re.compile(r".*\.run_tests$"),
        "count-loc": re.compile(r".*\.count_loc$"),
        "package": re.compile(r".*\.goals.package.package_asset"),
        "update-build-files": re.compile(r".*\.update_build_files$"),
        "dependees": re.compile(r".*\.dependees_goal$"),
    }

    _IGNORED_NAMES_REGEX = compile_expression(_IGNORED_NAMES)
    _IGNORED_ARTIFACTS_RULE_NAME_REGEX = compile_expression(_IGNORE_ARTIFACTS_RULE_NAMES)
    _IGNORED_ARTIFACTS_DESCRIPTION_REGEX = compile_expression(_IGNORE_ARTIFACTS_RULE_DESCRIPTION)
    # Order matters, junit xml results takes precedence over console since it will try to embed console (stdout/stderr) into test results artifact.
    _HANDLERS = (PytestJUnitXmlArtifactsHandler, ConsoleArtifactsHandler, XmlCoverageArtifactsHandler)
    MAX_FILES = 30

    @classmethod
    def create(cls) -> GoalArtifactsExtractor:
        return cls(handler_classes=cls._HANDLERS)

    def __init__(self, handler_classes: tuple[type[BaseHandler], ...]) -> None:
        self._handlers: tuple[BaseHandler, ...] = tuple(handler_cls() for handler_cls in handler_classes)
        self._standalone_names = frozenset(
            handler.standalone_name for handler in self._handlers if handler.standalone_name
        )

    @property
    def allowed_standalone_artifact_names(self) -> frozenset[str]:
        return self._standalone_names

    def _process_artifacts(self, run_id: str, artifacts_wu: WorkUnitWithArtifacts, goal: str) -> None:
        for handler in self._handlers:
            handled = handler.handle_work_unit_artifacts(artifacts_wu, goal)
            if handled:
                return
        _logger.warning(
            f"No artifact handler for {run_id=} artifacts_work_unit_id={artifacts_wu.work_unit['id']} {goal=}"
        )

    def _sort_wu_artifacts(self, wus: list[dict]) -> list[dict]:
        # priority first, then by outcome, Failure come first, so sorting by the first char works (since F S Z) then
        # Secondary sort is the name since it is unique.
        def sort_key(wu):
            return wu.get("priority", 1), wu.get("result", "Z")[0], wu["name"]

        sorted_wus = sorted(wus, key=sort_key)
        for wu in sorted_wus:
            wu.pop("priority", None)
        return sorted_wus

    def _finalize(self) -> tuple[list[FileInfo], dict]:
        files: list[FileInfo] = []
        work_units_by_goal = defaultdict(list)
        for handler in self._handlers:
            artifacts = handler.get_artifacts()
            files.extend(artifacts.files)
            for goal, work_units in artifacts.work_units_by_goal.items():
                work_units_by_goal[goal].extend(work_units)
        sorted_wus_by_goal = {goal: self._sort_wu_artifacts(wus) for goal, wus in work_units_by_goal.items()}
        return files, sorted_wus_by_goal

    def _get_run_artifacts(self, log_artifact_name: str | None, build_data: dict) -> tuple[list[FileInfo], dict]:
        artifacts_files: list[FileInfo] = []
        artifacts = {}

        def add_artifacts(artifact: RunArtifact) -> None:
            if not artifact:
                return
            artifact_file, artifact_desc = artifact
            artifacts_files.append(artifact_file)
            artifacts[artifact_desc["name"]] = [artifact_desc]

        add_artifacts(get_run_metrics(build_data, self._wu_map.values()))
        add_artifacts(get_pants_options(build_data))
        add_artifacts(get_targets(build_data))
        platform_info_file = get_platform_info(build_data)
        if platform_info_file:
            artifacts_files.append(platform_info_file)
        if log_artifact_name:
            artifacts["logs"] = [
                {
                    "name": "Logs",
                    "description": "Pants run log",
                    "artifacts": log_artifact_name,
                    "content_types": [RUN_LOGS_ARTIFACTS_CONTENT_TYPE],
                }
            ]
        return artifacts_files, artifacts

    def _init_handlers(self, start_time_usec: int) -> None:
        for handler in self._handlers:
            handler.init_processing(start_time_usec=start_time_usec)

    def get_artifacts(
        self,
        run_info: RunInfo,
        build_data: dict,
        log_artifact_name: str | None,
        standalone_artifacts: list[StandaloneArtifact] | None = None,
    ) -> ArtifactsExtractResult:
        self._wu_map = {wu["workunit_id"]: wu for wu in build_data.get("workunits", [])}  # type: ignore[union-attr]
        start_time_usec = min(wu["start_usecs"] for wu in self._wu_map.values()) if self._wu_map else -1
        self._init_handlers(start_time_usec)
        goals = run_info.computed_goals
        standalone_map = {artifact.workunit_id: artifact for artifact in standalone_artifacts or []}
        log_missing_goal_for_work_unit = True
        for artifact_wu in self._iter_artifact_workunits(standalone_map):
            goal_name = self._find_goal(
                goals,
                artifact_wu.significant_work_unit,
                log_warning=log_missing_goal_for_work_unit,
                run_id=run_info.run_id,
            )
            if not goal_name:
                log_missing_goal_for_work_unit = False
                continue
            self._process_artifacts(run_id=run_info.run_id, artifacts_wu=artifact_wu, goal=goal_name)
        artifacts_files, goals_wu_artifacts = self._finalize()
        if len(artifacts_files) > self.MAX_FILES:
            with push_scope() as scope:
                # This tells sentry to group all events from this message into a single issue.
                scope.fingerprint = ["buildsense", "artifacts", "max_files"]
                _logger.error(
                    f"extract_artifacts has too many files, not storing them. artifacts_files={len(artifacts_files)} goals={len(goals_wu_artifacts)} extracted for run_id={run_info.run_id} repo_id={run_info.repo_id}"
                )
            artifacts_files.clear()
            goals_wu_artifacts.clear()
        extra_files, extra_artifacts = self._get_run_artifacts(log_artifact_name, build_data)
        artifacts_files.extend(extra_files)
        goals_wu_artifacts.update(extra_artifacts)

        if not artifacts_files:
            return ArtifactsExtractResult(files=tuple(), has_metrics=False)
        wu_file = FileInfo.create_json_file("artifacts_work_units", goals_wu_artifacts)
        return ArtifactsExtractResult(
            files=tuple(artifacts_files) + (wu_file,), has_metrics="metrics" in extra_artifacts
        )

    def _match_goal(self, name: str, goals: list[str]) -> str | None:
        if name in goals:
            return name
        if "." in name:
            last_part = name.split(".")[-1]
            if last_part in goals:
                return last_part
        for goal in goals:
            alias_expression = self._GOALS_ALIASES.get(goal)
            if not alias_expression:
                continue
            if alias_expression.match(name):
                return goal
        return None

    def _find_goal(self, goals: list[str], work_unit: dict, log_warning: bool, run_id: str) -> str | None:
        attempted_names = []
        for parent in self._iter_parents(work_unit):
            name = parent["name"]
            goal = self._match_goal(name, goals)
            if goal:
                return goal
            attempted_names.append(name)
        if log_warning:
            attempted = ",".join(attempted_names)
            _logger.warning(f"Can't find goal work unit for {work_unit=} {goals=} {attempted=} {run_id=}")
        return None

    def _find_significant_parent(self, work_unit: dict) -> dict | None:
        for parent in self._iter_parents(work_unit):
            name = parent["name"]
            if self._IGNORED_ARTIFACTS_RULE_NAME_REGEX.match(name):
                return None
            if not self._IGNORED_NAMES_REGEX.match(name):
                return parent
        _logger.warning(f"Can't find significant parent for {work_unit=}")
        return None

    def _iter_artifact_workunits(
        self, standalone_artifacts_map: dict[str, StandaloneArtifact]
    ) -> Iterator[WorkUnitWithArtifacts]:
        for work_unit in self._wu_map.values():
            workunit_id = work_unit["workunit_id"]
            description = work_unit.get("description")
            if description and self._IGNORED_ARTIFACTS_DESCRIPTION_REGEX.match(description):
                continue
            artifacts = work_unit.get("artifacts")
            if not artifacts:
                standalone = standalone_artifacts_map.get(workunit_id)
                if not standalone:
                    continue
                artifacts = standalone.as_artifacts_dict()
            significant_parent = self._find_significant_parent(work_unit)
            if not significant_parent:
                continue
            yield WorkUnitWithArtifacts(
                work_unit=work_unit,
                significant_work_unit=significant_parent,
                artifacts=artifacts,
            )

    def _iter_parents(self, work_unit: dict) -> Iterator[dict]:
        while work_unit:
            yield work_unit
            # Pants is moving to support multiple parents IDs. see: https://github.com/pantsbuild/pants/pull/14856
            # However, we need to be able to support both old and new data, hence this logic.
            # Note that this depends on the logic in the plugin's  toolchain/pants/buildsense/converter.py which will move to using parent_ids
            # before pants does.
            if "parent_ids" in work_unit:  # noqa: SIM401
                parent_ids = work_unit["parent_ids"]
            else:  # parent_id can be None in the json, or it can be missing, so we need to handle both cases.
                parent_ids = [work_unit["parent_id"]] if work_unit.get("parent_id") else []
            if not parent_ids:
                return
            # For now, we are yielding only the first parent.
            work_unit = self._wu_map[parent_ids[0]]
