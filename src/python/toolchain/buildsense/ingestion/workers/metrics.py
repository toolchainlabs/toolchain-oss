# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.metrics_store import (
    MetricsStoreTransientError,
    MissingBucketError,
    PantsMetricsStore,
    PantsMetricsStoreManager,
)
from toolchain.buildsense.ingestion.models import ConfigureRepoMetricsBucket, IndexPantsMetrics
from toolchain.buildsense.ingestion.run_info_raw_store import BuildFile, RunInfoRawStore
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.common import METRICS_FILE_NAME
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PantsMetricsIndexer(Worker):
    work_unit_payload_cls = IndexPantsMetrics
    ALLOWED_GOALS = frozenset(("lint", "typecheck", "fmt", "test", "package", "check"))

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        return WorkExceptionCategory.TRANSIENT if isinstance(exception, MetricsStoreTransientError) else None

    def transient_error_retry_delay(
        self, work_unit_payload: IndexPantsMetrics, exception: Exception
    ) -> datetime.timedelta | None:
        return datetime.timedelta(minutes=40)

    def do_work(self, work_unit_payload: IndexPantsMetrics) -> bool:
        ipm = work_unit_payload
        if ipm.is_deleted:
            _logger.info(f"PantsMetricsIndexer {ipm} run is marked as deleted.")
            return True
        repo = Repo.get_for_id_or_none(repo_id=ipm.repo_id, include_inactive=True)
        if not repo:
            raise ToolchainAssertion(f"Could not load repo for {ipm}")
        if not repo.is_active:
            _logger.warning(f"Repo {repo} not active.")
            return True
        table = RunInfoTable.for_customer_id(repo.customer_id)
        run_info = table.get_by_run_id(repo_id=ipm.repo_id, user_api_id=ipm.user_api_id, run_id=ipm.run_id)
        if not run_info:
            raise ToolchainAssertion(f"Couldn't load build for {ipm}")
        user = ToolchainUser.get_by_api_id(api_id=run_info.user_api_id, include_inactive=True)
        metrics_store = PantsMetricsStore.for_repo(repo)
        metrics_file = self._get_metrics(repo, run_info)
        try:
            metrics_store.store_metrics(run_info=run_info, user=user, metrics_file=metrics_file)
        except MissingBucketError as error:
            _logger.warning(f"Can't index pants metrics for {ipm} - missing bucket {error!r}")
            return False
        return True

    def on_reschedule(self, work_unit_payload: IndexPantsMetrics) -> None:
        crmb = ConfigureRepoMetricsBucket.run_for_repo(repo_id=work_unit_payload.repo_id)
        work_unit_payload.add_requirement_by_id(crmb.work_unit_id)

    def _get_metrics(self, repo: Repo, run_info: RunInfo) -> BuildFile | None:
        info_store = RunInfoRawStore.for_repo(repo=repo)
        return info_store.get_named_data(run_info=run_info, name=f"{METRICS_FILE_NAME}.json", optional=True)


class PantsMetricsConfigurator(Worker):
    work_unit_payload_cls = ConfigureRepoMetricsBucket

    def do_work(self, work_unit_payload: ConfigureRepoMetricsBucket) -> bool:
        repo_id = work_unit_payload.repo_id
        repo = Repo.get_for_id_or_none(repo_id=repo_id, include_inactive=True)
        if not repo:
            raise ToolchainAssertion(f"Can't find repo for {repo_id}")
        mgr = PantsMetricsStoreManager.for_repo(repo)
        if repo.is_active:
            _logger.info(f"Init metrics bucket for {repo}")
            mgr.init_bucket(recreate=False, retention_days=365)
        else:
            _logger.info(f"Delete metrics bucket for {repo}")
            mgr.delete_bucket()
        return True
