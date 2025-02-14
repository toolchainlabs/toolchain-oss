# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import replace
from pathlib import PurePath

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.batched_builds_queue import BatchedBuildsQueue, QueuedBuilds
from toolchain.buildsense.ingestion.integrations.ci_scm_helpers import ScmInfoHelper
from toolchain.buildsense.ingestion.models import IndexPantsMetrics, MoveBuild, ProcessPantsRun, ProcessQueuedBuilds
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion, RequestContext
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.processor import ProcessRunResults, process_pants_run
from toolchain.buildsense.records.run_info import RunInfo, ScmProvider
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PantsRunProcessor(Worker):
    work_unit_payload_cls = ProcessPantsRun

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._results: ProcessRunResults | None = None
        self._move_build_user: ToolchainUser | None = None
        self._run_info: RunInfo | None = None
        self._repo: Repo | None = None

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: ProcessPantsRun, exception: Exception
    ) -> datetime.timedelta | None:
        return datetime.timedelta(minutes=3)

    def do_work(self, work_unit_payload: ProcessPantsRun) -> bool:
        ppr: ProcessPantsRun = work_unit_payload
        if ppr.is_deleted:
            _logger.info(f"PantsRunProcessor {ppr} run is marked as deleted.")
            return True
        repo = Repo.get_or_none(id=ppr.repo_id)
        if not repo or not repo.customer.is_active:
            _logger.warning(f"repo ({ppr.repo_id}) for {ppr} is unknown or inactive.")
            return True
        table = RunInfoTable.for_customer_id(repo.customer_id)
        self._repo = repo
        scm = ScmProvider(repo.customer.scm_provider.value)
        self._run_info = table.get_by_run_id(repo_id=ppr.repo_id, user_api_id=ppr.user_api_id, run_id=ppr.run_id)
        if not self._run_info:
            raise ToolchainAssertion(f"Couldn't load build for {ppr}")
        self._move_build_user = self._check_ci_user(self._run_info)
        if self._move_build_user:
            return False
        self._results = process_pants_run(self._run_info, scm)
        return True

    def _check_ci_user(self, run_info: RunInfo) -> ToolchainUser | None:
        if not run_info.ci_info:
            return None
        build_data = RunInfoRawStore.for_run_info(run_info).get_build_data(run_info)
        scm = ScmInfoHelper(customer_id=run_info.customer_id, repo_id=run_info.repo_id, silence_timeouts=False)
        user = ToolchainUser.get_by_api_id(api_id=run_info.user_api_id, include_inactive=True)
        _, ci_user = scm.get_ci_info(run_id=run_info.run_id, build_stats=build_data, auth_user=user, ci_user=None)
        if not ci_user:
            _logger.warning(f"Unable to determine CI user for run: {run_info.run_id}")
            return None
        return ci_user if ci_user.api_id != user.api_id else None

    def on_reschedule(self, work_unit_payload: ProcessPantsRun) -> None:
        if not self._move_build_user or not self._run_info:  # This check is mostly to silence mypy
            raise ToolchainAssertion("on_reschedule called but move_build_user is not set")
        move_build = MoveBuild.create(run_info=self._run_info, to_user_api_id=self._move_build_user.api_id)
        work_unit_payload.add_requirement_by_id(move_build.work_unit_id)
        work_unit_payload.user_api_id = self._move_build_user.api_id
        work_unit_payload.save()

    def on_success(self, work_unit_payload: ProcessPantsRun) -> None:
        if not self._results or not self._repo:
            return
        self._store_updated(self._results, self._repo)

    def _store_updated(self, results: ProcessRunResults, repo: Repo) -> None:
        updated_run_info = results.run_info
        table = RunInfoTable.for_customer_id(updated_run_info.customer_id, allow_overwrites=True)
        table.save_run(updated_run_info)
        info_store = RunInfoRawStore.for_run_info(updated_run_info)
        for fn in results.files_to_delete:
            info_store.delete_named_data(run_info=updated_run_info, name=fn)  # type: ignore[arg-type]
        _logger.info(
            f"store_updated: {updated_run_info.run_id} has_metrics={results.has_metrics} files_to_delete={len(results.files_to_delete)}"
        )
        if results.has_metrics:
            IndexPantsMetrics.create_or_rerun(run_info=updated_run_info, repo=repo)


class QueuedBuildsProcessor(Worker):
    work_unit_payload_cls = ProcessQueuedBuilds

    def do_work(self, work_unit_payload: ProcessQueuedBuilds) -> bool:
        pqb: ProcessQueuedBuilds = work_unit_payload
        repo = Repo.get_or_none(id=pqb.repo_id)
        if not repo:
            raise ToolchainAssertion(f"Could not load repo for {pqb}")
        builds_queue = BatchedBuildsQueue.for_repo(repo)
        builds = builds_queue.get_builds(pqb.key)
        stored_builds_count = self._ingest_builds(repo, builds)
        _logger.info(f"{pqb.work_unit} {stored_builds_count=} builds_count={len(builds.builds)}")
        return True

    def _ingest_builds(self, repo: Repo, builds: QueuedBuilds) -> int:
        user = ToolchainUser.get_by_api_id(builds.user_api_id, include_inactive=True)
        pdi = PantsDataIngestion.for_repo(repo)
        saved_count = 0
        for build_stats in builds.get_build_stats():
            request_ctx = RequestContext(
                request_id=builds.request_id,
                stats_version="3",
                client_ip=None,
                accept_time=builds.accepted_time,
                content_length=130_300_200,
            )
            saved = pdi.store_build_ended(
                build_stats=build_stats,
                user=user,
                impersonated_user=None,
                request_ctx=request_ctx,
                ignore_dups=True,
            )
            if saved:
                saved_count += 1
        return saved_count


class BuilderMover(Worker):
    work_unit_payload_cls = MoveBuild

    def do_work(self, work_unit_payload: MoveBuild) -> bool:
        """Copy and delete the build in s3 and DynamoDB We can't change data in place so we have to copy and then
        delete.

        Order matters since s3 is the baseline so we write there first and delete from it last. We can always re-create
        (with some stuff missing) the data in DynamoDB bases on the data in s3 (see import_builds.py). The order ensures
        that we minimize the risk of data discrepancy and in the case it occurs we can (manually, right now) recover
        from it.
        """
        mv_build: MoveBuild = work_unit_payload
        repo = Repo.get_or_none(id=mv_build.repo_id)
        if not repo:
            raise ToolchainAssertion(f"Could not load repo for {mv_build}")
        table = RunInfoTable.for_customer_id(repo.customer_id)
        old_run_info = table.get_by_run_id(
            repo_id=mv_build.repo_id, user_api_id=mv_build.from_user_api_id, run_id=mv_build.run_id
        )
        if not old_run_info:
            _logger.warning(f"Couldn't load build for {mv_build}")
            return True
        build_file_names = self._get_old_build_files(old_run_info)
        new_run_info = self._copy_build_to_new_location(
            old_run_info, names=build_file_names, new_user_api_id=mv_build.to_user_api_id
        )
        table.save_run(new_run_info)
        _logger.info(f"moved build {mv_build} --> {new_run_info}")
        table.delete_build(
            repo_id=old_run_info.repo_id, user_api_id=old_run_info.user_api_id, run_id=old_run_info.run_id
        )
        store = RunInfoRawStore.for_run_info(old_run_info)
        store.delete_build_data(run_info=old_run_info, dry_run=False)
        return True

    def _get_old_build_files(self, run_info: RunInfo) -> tuple[str, ...]:
        store = RunInfoRawStore.for_run_info(run_info)
        files_keys = store.list_files(run_info)
        old_s3_key = run_info.server_info.s3_key
        if old_s3_key not in files_keys:
            raise ToolchainAssertion(f"Can't find {old_s3_key} in {files_keys}")
        return tuple(PurePath(fk).name for fk in files_keys)

    def _copy_build_to_new_location(
        self, old_run_info: RunInfo, names: tuple[str, ...], new_user_api_id: str
    ) -> RunInfo:
        store = RunInfoRawStore.for_run_info(old_run_info)
        new_run_info = replace(old_run_info, user_api_id=new_user_api_id)
        for name in names:
            build_file = store.get_named_data(old_run_info, name)
            if not build_file:
                raise ToolchainAssertion(f"Can't load build data for run_id={old_run_info.run_id} {name=}")
            _, new_s3_key = store.save_build_file(
                run_id=old_run_info.run_id,
                content_or_file=build_file.content,
                content_type=build_file.content_type,
                name=name,
                user_api_id=new_user_api_id,
                mode=WriteMode.OVERWRITE,
                dry_run=False,
                is_compressed=False,
                metadata=build_file.metadata,
            )
            if old_run_info.server_info.s3_key == build_file.s3_key:
                new_run_info.server_info = replace(old_run_info.server_info, s3_key=new_s3_key)
        return new_run_info
