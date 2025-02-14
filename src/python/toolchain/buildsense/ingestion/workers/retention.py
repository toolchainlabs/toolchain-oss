# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from django.conf import settings

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.models import IndexPantsMetrics, ProcessBuildDataRetention, ProcessPantsRun
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.records.run_info import RunKey
from toolchain.buildsense.search.run_info_search_index import RunInfoSearchIndex, SearchTransientError
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.site.models import Repo
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)

transaction = TransactionBroker("buildsense")


class BuildDataRetention(Worker):
    work_unit_payload_cls = ProcessBuildDataRetention
    _MAX_BUILDS_PER_RUN = 20  # Mostly due to the limit (25) on dynamodb batch_write_item API which we use here.
    _DELAY_BEFORE_FOLLOW_UP_DELETE = datetime.timedelta(minutes=5)
    OPENSEARCH_TIMEOUT_SEC = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._deleted_count = 0

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception) or isinstance(exception, SearchTransientError):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: ProcessBuildDataRetention, exception: Exception
    ) -> datetime.timedelta | None:
        return datetime.timedelta(minutes=30)

    def do_work(self, work_unit_payload: ProcessBuildDataRetention) -> bool:
        bdr: ProcessBuildDataRetention = work_unit_payload
        repo = Repo.get_for_id_or_none(repo_id=bdr.repo_id, include_inactive=True)
        if not repo:
            raise ToolchainAssertion(f"Repo {bdr.repo_id} not found")
        delete_all = bdr.retention_days == 0
        if delete_all:
            latest_date = None
        else:
            latest_date = (utcnow() - datetime.timedelta(days=bdr.retention_days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - datetime.timedelta(days=1)
        run_keys = self._get_builds_to_delete(repo, latest_date=latest_date)
        self._deleted_count = self._delete_builds(repo=repo, run_keys=run_keys, dry_run=bdr.dry_run)
        _logger.info(
            f"BuildDataRetention: deleted items {repo.full_name} - repo_id={repo.id}: {self._deleted_count} dry_run={bdr.dry_run}"
        )
        if not repo.is_active and delete_all and self._deleted_count == 0:
            _logger.info(f"Finished deleting all data for inactive repo: {repo.full_name}")
            return True
        if bdr.period_minutes is not None:
            return False
        if bdr.dry_run:
            # For dry runs, we don't want to re-run the WU otherwise it will run for ever
            # Since we don't actually delete data, ES will return the same data to delete in the next run
            return True
        return self._deleted_count == 0

    def _delete_builds(self, repo: Repo, run_keys: tuple[RunKey, ...], dry_run: bool) -> int:
        if not run_keys:
            _logger.warning(f"no run keys to delete for {repo.full_name}")
            return 0
        table = RunInfoTable.for_customer_id(repo.customer_id)
        info_store = RunInfoRawStore.for_repo(repo)
        run_infos = table.get_by_run_ids(run_keys=run_keys, repo_id=repo.id)
        if len(run_infos) != len(run_keys):
            _logger.warning(
                f"Couldn't load all requested rows for {repo.full_name} requested={len(run_keys)} loaded={len(run_infos)}"
            )
        self.mark_build_delete(repo=repo, run_keys=run_keys)
        if not dry_run:
            table.delete_builds(run_keys=run_keys)
        for run_info in run_infos:
            info_store.delete_build_data(run_info=run_info, dry_run=dry_run)
        return len(run_infos)

    def _get_builds_to_delete(self, repo: Repo, latest_date: datetime.datetime | None) -> tuple[RunKey, ...]:
        search_index = RunInfoSearchIndex.for_customer_id(
            settings, repo.customer_id, timeout_in_sec=self.OPENSEARCH_TIMEOUT_SEC
        )
        results = search_index.search_all_matching(
            repo_id=repo.id,
            field_map={},
            earliest=None,
            latest=latest_date,
            page_size=self._MAX_BUILDS_PER_RUN,
        )
        date_marker = f"latest_date={latest_date.isoformat()}" if latest_date else "ALL"
        _logger.info(
            f"selected builds for deletion from {repo} {date_marker} count={results.count} total={results.total_count}"
        )
        return results.items

    def mark_build_delete(self, repo: Repo, run_keys: tuple[RunKey, ...]):
        with transaction.atomic():
            # This is not the most effiecent way to do it (in terms of the number of DB roundtrips).
            # However, we only delete <21 builds in a single run. so I think this is ok for now as we I don't expect this code to be running a lot or to cause any DB load issues.
            for run_key in run_keys:
                ipm = IndexPantsMetrics.get_or_none(
                    repo_id=repo.id,
                    user_api_id=run_key.user_api_id,
                    run_id=run_key.run_id,
                )
                if ipm:
                    ipm.mark_as_deleted()
                ppr = ProcessPantsRun.get_or_none(
                    repo_id=repo.id,
                    user_api_id=run_key.user_api_id,
                    run_id=run_key.run_id,
                )
                if ppr:
                    ppr.mark_as_deleted()

    def on_reschedule(self, work_unit_payload: ProcessBuildDataRetention) -> datetime.datetime | None:
        data_retention: ProcessBuildDataRetention = work_unit_payload
        now = utcnow()
        if self._deleted_count > 0:
            # we have more data to delete, so do it in 10m (to avoid creating load on dynamodb and ES)
            # and to allow enough time for dynamodb_to_es_lambda to propgate deletions from DynamoDB to ES.
            return now + self._DELAY_BEFORE_FOLLOW_UP_DELETE
        # Nothing more to delete, so schedule in the next internval to check if there is data to delete.
        return now + datetime.timedelta(minutes=data_retention.period_minutes)
