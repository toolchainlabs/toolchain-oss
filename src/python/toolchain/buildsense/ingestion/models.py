# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from enum import Enum, unique

from django.db.models import BooleanField, CharField, Index, PositiveIntegerField

from toolchain.buildsense.records.run_info import RunInfo
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.site.models import Repo
from toolchain.django.util.helpers import get_choices
from toolchain.workflow.models import WorkUnit, WorkUnitPayload

_logger = logging.getLogger(__name__)

transaction = TransactionBroker("buildsense")


@unique
class RunState(Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class ProcessPantsRun(WorkUnitPayload):
    repo_id = CharField(max_length=64)
    user_api_id = CharField(max_length=22)
    run_id = CharField(max_length=512)
    # _state is used by django internally.
    _run_state = CharField(
        max_length=10, default=RunState.ACTIVE.value, db_column="state", choices=get_choices(RunState)
    )
    # For Admin UI (toolshed) and __str__ display purposes only. value will be: customer_slug/repo_sug
    repo_full_name = CharField(max_length=120, null=True, default=None)  # noqa: DJ01

    @classmethod
    def create(cls, run_info: RunInfo, repo: Repo) -> ProcessPantsRun:
        ppr = cls.objects.create(
            repo_id=run_info.repo_id,
            user_api_id=run_info.user_api_id,
            run_id=run_info.run_id,
            _run_state=RunState.ACTIVE.value,
            repo_full_name=repo.full_name,
        )
        _logger.info(
            f"queue_pants_run_proessing wu_id={ppr.work_unit_id} run_id={run_info.run_id} repo={repo.full_name} repo_id={run_info.repo_id}"
        )
        return ppr

    @property
    def description(self) -> str:
        return f"repo={self.repo_full_name or 'N/A'} run_id={self.run_id} repo_id={self.repo_id} user_api_id={self.user_api_id}"

    @property
    def state(self) -> RunState:
        return RunState(self._run_state)

    @property
    def is_deleted(self) -> bool:
        return self.state == RunState.DELETED

    def mark_as_deleted(self) -> bool:
        if self.is_deleted:
            return False
        self._run_state = RunState.DELETED.value
        self.save()
        return True


class ProcessQueuedBuilds(WorkUnitPayload):
    repo_id = CharField(max_length=64)
    bucket = CharField(max_length=64)
    key = CharField(max_length=512)
    num_of_builds = PositiveIntegerField()

    @classmethod
    def create(cls, repo: Repo, bucket: str, key: str, num_of_builds: int) -> ProcessQueuedBuilds:
        return cls.objects.create(repo_id=repo.id, bucket=bucket, key=key, num_of_builds=num_of_builds)

    @property
    def description(self) -> str:
        return f"num_of_builds={self.num_of_builds} key={self.key}"


class IndexPantsMetrics(WorkUnitPayload):
    repo_id = CharField(max_length=64)
    user_api_id = CharField(max_length=22)
    run_id = CharField(max_length=512)
    # _state is used by django internally.
    _run_state = CharField(
        max_length=10, default=RunState.ACTIVE.value, db_column="state", choices=get_choices(RunState)
    )
    # For Admin UI (toolshed) and __str__ display purposes only. value will be: customer_slug/repo_sug
    repo_full_name = CharField(max_length=120, null=True, default=None)  # noqa: DJ01

    class Meta:
        indexes = [Index(fields=["repo_id", "run_id"])]

    @classmethod
    def create_or_rerun(cls, run_info: RunInfo, repo: Repo) -> IndexPantsMetrics:
        ipm, created = cls.objects.get_or_create(
            repo_id=run_info.repo_id,
            user_api_id=run_info.user_api_id,
            run_id=run_info.run_id,
            defaults={"repo_full_name": repo.full_name},
        )
        _logger.info(
            f"queue_index_pants_metrics {created=} wu_id={ipm.work_unit_id} state={ipm.work_unit.state} run_id={run_info.run_id} repo_id={run_info.repo_id}"
        )
        if not created and ipm.work_unit.state == WorkUnit.SUCCEEDED:
            ipm.rerun_work_unit()
        return ipm

    @property
    def description(self) -> str:
        return f"repo={self.repo_full_name or 'N/A'} run_id={self.run_id} repo_id={self.repo_id} user_api_id={self.user_api_id}"

    @property
    def state(self) -> RunState:
        return RunState(self._run_state)

    @property
    def is_deleted(self) -> bool:
        return self.state == RunState.DELETED

    def mark_as_deleted(self) -> bool:
        if self.is_deleted:
            return False
        self._run_state = RunState.DELETED.value
        self.save()
        return True


class ProcessBuildDataRetention(WorkUnitPayload):
    _DEFAULT_RETENTION_DAYS = 365 * 25  # Default - 25 years. should be enough.
    repo_id = CharField(max_length=64, editable=False, unique=True)
    # For how many days we keep builds. builds older than `retention_days` will be deleted.
    retention_days = PositiveIntegerField(default=_DEFAULT_RETENTION_DAYS)
    # Trigger DeleteRepoBuildsData every this many minutes (or None for one-time processing).
    period_minutes = PositiveIntegerField(null=True)

    # By default we run without deleting anything.
    dry_run = BooleanField(default=True)
    # For Admin UI (toolshed) and __str__ display purposes only. value will be: customer_slug/repo_sug
    repo_full_name = CharField(max_length=120, null=True, default=None)  # noqa: DJ01

    @classmethod
    def create_or_update_for_repo(
        cls, *, repo: Repo, retention_days: int | None = None, period_minutes: int | None = None, dry_run: bool = True
    ) -> ProcessBuildDataRetention:
        obj, created = cls.objects.update_or_create(
            repo_id=repo.id,
            defaults={
                "retention_days": cls._DEFAULT_RETENTION_DAYS if retention_days is None else retention_days,
                "period_minutes": period_minutes,
                "dry_run": dry_run,
                "repo_full_name": repo.full_name,
            },
        )
        _logger.info(f"condigure {cls.__name__} for {obj.description}. {created=}")
        if not created and obj.work_unit.state == WorkUnit.SUCCEEDED:
            obj.rerun_work_unit()
        return obj

    @property
    def description(self) -> str:
        rate_str = f"run every {self.period_minutes} minutes" if self.period_minutes else "run once"
        return f"repo={self.repo_full_name or 'N/A'} repo_id={self.repo_id} retention {self.retention_days:,} days. {rate_str}. dry_run={self.dry_run}"

    def __str__(self) -> str:
        return self.description


class ConfigureRepoMetricsBucket(WorkUnitPayload):
    repo_id = CharField(max_length=64, editable=False, unique=True)

    @classmethod
    def run_for_repo(cls, *, repo_id: str) -> ConfigureRepoMetricsBucket:
        obj, created = cls.objects.get_or_create(repo_id=repo_id)
        if created:
            _logger.info(f"Create {cls.__name__} for {repo_id=}")
            return obj
        if obj.work_unit.state == WorkUnit.SUCCEEDED:
            obj.rerun_work_unit()
        return obj


class MoveBuild(WorkUnitPayload):
    repo_id = CharField(max_length=22)
    run_id = CharField(max_length=512)
    from_user_api_id = CharField(max_length=22)
    to_user_api_id = CharField(max_length=22)

    @classmethod
    def create(cls, run_info: RunInfo, to_user_api_id: str) -> ProcessPantsRun:
        move_build = cls.objects.create(
            repo_id=run_info.repo_id,
            run_id=run_info.run_id,
            from_user_api_id=run_info.user_api_id,
            to_user_api_id=to_user_api_id,
        )
        _logger.info(f"create move_build wu_id={move_build.work_unit_id} {str(move_build)}")
        return move_build

    @property
    def description(self) -> str:
        return f"run_id={self.run_id} repo_id={self.repo_id} from_user_api_id={self.from_user_api_id} to_user_api_id={self.to_user_api_id}"


_MODELS_TO_CHECK = [ProcessPantsRun]


def check_ingestion_models_access() -> dict:
    data = {model.__name__: model.objects.count() for model in _MODELS_TO_CHECK}
    return data
