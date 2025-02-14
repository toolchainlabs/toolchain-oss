# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from toolchain.base.contexttimer import Timer
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import ServiceBuildResult, ToolchainPythonService, extrapolate_python_services
from toolchain.util.pants.runner import PantsRunner
from toolchain.util.prod.git_tools import (
    CommitInfo,
    InvalidCommitSha,
    get_commits_with_files,
    has_local_changes,
    is_latest_upstream_master,
    iter_changed_files,
)
from toolchain.util.prod.helm_charts import HelmChart, ServiceChartInfo

_logger = logging.getLogger(__name__)


ServicesVersions = dict[str, tuple[str, str]]  # service: (current version, new version)
ChangeMessages = tuple[tuple[str, Optional[str]], ...]


@dataclass(frozen=True)
class ChangeLog:
    _PR_NUMBER_EXP = re.compile(r".*\(#(?P<pr>\d+)\)$")
    from_sha: str
    to_sha: str
    changes: tuple[CommitInfo, ...]

    @classmethod
    def empty(cls) -> ChangeLog:
        return ChangeLog(changes=tuple(), from_sha="", to_sha="")

    def get_pr_link(self, commit: CommitInfo) -> str | None:
        match = self._PR_NUMBER_EXP.match(commit.message)
        if not match:
            return None
        pr_number = match.group("pr")
        return f"https://github.com/toolchainlabs/toolchain/pull/{pr_number}/"

    def list_changes(self) -> tuple[str, ...]:
        return tuple(str(ci) for ci in self.changes)

    def get_changes(self) -> ChangeMessages:
        return tuple((commit.message, self.get_pr_link(commit)) for commit in self.changes)


class ChangeHelper:
    MIGRATION_LEAD_SVC = "toolshed"
    THIRD_PARTY_DEP = "3rdparty"

    @classmethod
    def create(cls, aws_region: str) -> ChangeHelper:
        lead_svc = extrapolate_python_services([cls.MIGRATION_LEAD_SVC])[0]
        lead_chart = ServiceChartInfo.for_service(lead_svc)
        return cls(aws_region=aws_region, migration_lead=lead_chart)

    def __init__(self, aws_region: str, migration_lead: ServiceChartInfo) -> None:
        self._aws_region = aws_region
        self._migration_lead = migration_lead

    @classmethod
    def check_git_state(cls) -> bool:
        git_state_ok = True
        if has_local_changes():
            _logger.error("Local git changes detected.")
            git_state_ok = False
        if not is_latest_upstream_master():
            _logger.error("Current branch is not lastest upstream/master.")
            git_state_ok = False
        return git_state_ok

    def get_changes_for_paths(self, from_sha: str, to_sha: str, changes_paths: tuple[Path, ...]) -> ChangeLog:
        paths = tuple(rf"^{cp.as_posix()}" for cp in changes_paths)
        try:
            commits = tuple(get_commits_with_files(from_sha, to_sha, paths))
        except InvalidCommitSha as error:
            _logger.warning(f"Failed to get changelog: {error}")
            return ChangeLog.empty()
        return ChangeLog(from_sha=from_sha, to_sha=to_sha, changes=commits)

    def get_changes_for_service(self, chart_values: dict, build_result: ServiceBuildResult) -> ChangeLog:
        service = build_result.service
        if not isinstance(service, ToolchainPythonService):
            return ChangeLog.empty()
        chart_param = build_result.chart_parameters[0]
        image_tag = chart_values[chart_param][self._aws_region]
        if not image_tag:
            _logger.warning("No current version to compare to.")
            return ChangeLog.empty()
        *_, old_revision = image_tag.rpartition("-")
        return self.get_changes_for_python_target(
            from_sha=old_revision, to_sha=build_result.commit_sha, target=service.pants_target
        )

    def get_changes_for_python_target(self, from_sha: str, to_sha: str, target: str) -> ChangeLog:
        pants = PantsRunner()
        with Timer() as timer:
            dependencies = set(pants.get_dependencies(target, third_party_filter=self.THIRD_PARTY_DEP))
        _logger.info(f"{target} has {len(dependencies)} dependencies (took {timer.elapsed:.3f} seconds)")
        commits = get_commits_with_files(from_sha, to_sha, (r"^src/python/",))
        relevant_commits = tuple(commit for commit in commits if dependencies.intersection(commit.changed_files))
        return ChangeLog(from_sha=from_sha, to_sha=to_sha, changes=relevant_commits)

    def check_pending_migrations(self, services_versions: ServicesVersions) -> bool:
        target_versions = {vers[1] for vers in services_versions.values()}
        if len(target_versions) > 1:
            raise ToolchainAssertion(f"More than one target version: {target_versions}.  This is not supported")
        pending_migrations = self.get_services_with_migrations(services_versions)
        if not pending_migrations:
            return True
        if pending_migrations == [self._migration_lead.service_name]:
            return True
        if not self._lead_has_pending_migrations(target_versions.pop()):
            return True
        _logger.warning(
            f"The following services have pending migrations: {pending_migrations}. {self._migration_lead.service_name} need to be deployed first so migrations can run before "
        )
        return False

    def _lead_has_pending_migrations(self, target_version: str) -> bool:
        values = HelmChart.get_chart_values(self._migration_lead.chart_path)
        image_tag = values["gunicorn_image_rev"][self._aws_region]
        from_version = image_tag[image_tag.rfind("-") + 1 :]
        return self._has_migrations(from_version, target_version)

    @classmethod
    def get_services_with_migrations(cls, services_versions: ServicesVersions) -> list[str]:
        return [service for service, versions in services_versions.items() if cls._has_migrations(*versions)]

    @classmethod
    def _has_migrations(cls, from_sha: str, to_sha: str) -> bool:
        for fn in iter_changed_files(from_sha, to_sha):
            if not fn.startswith("src/python/toolchain/"):
                continue
            if "/migrations/" in fn:
                return True
        return False
