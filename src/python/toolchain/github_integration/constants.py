# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from enum import Enum, unique

from dateutil.parser import parse

_logger = logging.getLogger(__name__)
GITHUB_INTEGRATION_DJANGO_APP = "toolchain.github_integration.apps.GithubIntegrationAppConfig"


@dataclass(frozen=True)
class GithubActionsCheckRun:
    _RUN_STATUSES = {"in_progress", "queued", "completed"}
    run_id: str
    suite_id: str
    status: str
    head_sha: str
    repository_id: str
    conclusion: str | None
    started_at: datetime.datetime

    @classmethod
    def from_json_dict(cls, json_data: dict) -> GithubActionsCheckRun:
        repo_id = str(json_data["repository"]["id"])
        check_run = json_data["check_run"]
        suite_id = str(check_run["check_suite"]["id"])
        run_id = str(check_run["id"])
        status = check_run["status"]
        if status not in cls._RUN_STATUSES:
            _logger.warning(f"unexpected_check_run_status {status=} {suite_id=} {run_id=}")
        started_at = parse(check_run["started_at"], ignoretz=True).replace(tzinfo=datetime.timezone.utc)
        return cls(
            run_id=run_id,
            suite_id=suite_id,
            status=status,
            repository_id=repo_id,
            started_at=started_at,
            head_sha=check_run["head_sha"],
            conclusion=check_run["conclusion"],
        )


@unique
class DataSource(Enum):
    API = "api"
    STORE = "store"


@dataclass(frozen=True)
class GithubActionsWorkflowRun:
    run_id: str
    run_number: str
    event: str
    status: str
    check_suite_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    repo_id: str
    head_sha: str
    source: DataSource
    last_fetch_time: datetime.datetime
    possibly_unique_values: str
    url: str

    @classmethod
    def from_json_dict(
        cls, source: DataSource, fetch_time: datetime.datetime, json_data: dict
    ) -> GithubActionsWorkflowRun:
        created_at = parse(json_data["created_at"])
        updated_at = parse(json_data["updated_at"])
        head_sha = json_data["head_sha"]
        run_id = str(json_data["id"])
        run_number = str(json_data["run_number"])
        possibly_unique_values = f"check_suite_node_id={json_data['check_suite_node_id']} node_id={json_data['node_id']} workflow_id={json_data['workflow_id']} {head_sha=} {run_id=} {run_number=}"
        return cls(
            run_id=run_id,
            run_number=run_number,
            event=json_data["event"],
            status=json_data["status"],
            # Note that check_suite_id being in the response is undocumented.
            check_suite_id=str(json_data["check_suite_id"]),
            created_at=created_at,
            updated_at=updated_at,
            repo_id=str(json_data["repository"]["id"]),
            head_sha=head_sha,
            source=source,
            last_fetch_time=fetch_time,
            possibly_unique_values=possibly_unique_values,
            url=json_data["html_url"],
        )

    @property
    def is_pull_request(self) -> bool:
        return self.event == "pull_request"

    @property
    def is_running_or_queued(self) -> bool:
        return self.status in {"in_progress", "queued"}

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"
