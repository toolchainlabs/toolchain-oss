# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from datetime import datetime, timedelta

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.pypi.models import PeriodicallyUpdateLevelDb, UpdateLevelDb
from toolchain.util.file.create import create_directory
from toolchain.util.leveldb.urls import input_list_base, leveldb_for_ordinal, ordinal_from_input_list
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker


class PeriodicLevelDbUpdater(Worker):
    work_unit_payload_cls = PeriodicallyUpdateLevelDb

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._latest_leveldb_url: str | None = None
        self._new_leveldb_url = ""

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: PeriodicallyUpdateLevelDb, exception: Exception
    ) -> timedelta | None:
        # Crawl is not time critical, so it is better to back of for a few minutes and let things recover.
        return timedelta(minutes=12)

    @staticmethod
    def latest_valid_ordinal(base_dir_url: str) -> int:
        input_lists_dir = create_directory(input_list_base(base_dir_url))
        input_list_file_urls = [x.url() for x in input_lists_dir.list()]
        if not input_list_file_urls:
            return -1
        latest_input_list_dir = max(input_list_file_urls)  # Filenames are ordered.
        return ordinal_from_input_list(latest_input_list_dir)

    def _resolve_leveldb_urls(self, work_unit_payload: PeriodicallyUpdateLevelDb) -> None:
        rebuild = work_unit_payload.rebuild
        latest_ordinal = self.latest_valid_ordinal(work_unit_payload.output_dir_base_url)
        if latest_ordinal == -1 or rebuild:
            self._latest_leveldb_url = None
        else:
            self._latest_leveldb_url = leveldb_for_ordinal(work_unit_payload.output_dir_base_url, latest_ordinal)
        self._new_leveldb_url = leveldb_for_ordinal(work_unit_payload.output_dir_base_url, latest_ordinal + 1)

    def do_work(self, work_unit_payload: PeriodicallyUpdateLevelDb) -> bool:
        # Start at the most recent serial we've definitely handled in either an incremental or full crawl.
        if work_unit_payload.period_minutes is None and work_unit_payload.work_unit.requirements.exists():
            # We were a one-time processing, and we've already created our requirement UpdateLevelDb, so we're done.
            return True
        self._resolve_leveldb_urls(work_unit_payload)
        # Note that if we're not a one-time processing we never succeed, but keep scheduling changelog processing forever.
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyUpdateLevelDb) -> datetime | None:
        work_unit_payload.disable_rebuild()
        update_leveldb_work = UpdateLevelDb.create(
            input_dir_url=work_unit_payload.input_dir_url,
            output_dir_url=self._new_leveldb_url,
            existing_leveldb_dir_url=self._latest_leveldb_url,
            builder_cls=work_unit_payload.builder_cls,
        )
        work_unit_payload.add_requirement_by_id(update_leveldb_work.work_unit_id)
        if work_unit_payload.period_minutes is not None:
            return utcnow() + timedelta(minutes=work_unit_payload.period_minutes)
        return None
