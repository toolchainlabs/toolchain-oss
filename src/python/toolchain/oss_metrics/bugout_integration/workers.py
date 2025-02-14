# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import utcnow
from toolchain.oss_metrics.bugout_integration.client import BugoutClient, TransientBugoutError
from toolchain.oss_metrics.bugout_integration.data_store import BugoutDataStore
from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


def _to_datetime(day: datetime.datetime) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time(), tzinfo=datetime.timezone.utc)


class BugoutDayDataDownloader(Worker):
    work_unit_payload_cls = DownloadBugoutDataForDay

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        return WorkExceptionCategory.TRANSIENT if isinstance(exception, TransientBugoutError) else None

    def transient_error_retry_delay(
        self, work_unit_payload: DownloadBugoutDataForDay, exception: Exception
    ) -> datetime.timedelta:
        return datetime.timedelta(minutes=10)

    def lease_secs(self, work_unit) -> float:
        return datetime.timedelta(hours=4).total_seconds()

    def do_work(self, work_unit_payload: DownloadBugoutDataForDay) -> bool:
        day = work_unit_payload.day
        next_day = day + datetime.timedelta(days=1)
        now = utcnow()
        if next_day == now.date() and now.hour < 2:
            # Don't download yesterday's data before 2am the next day to allow some lag time in processing the data on the bugout side
            return False
        journal_id = work_unit_payload.journal_id
        client = BugoutClient.for_django_settings(journal_id)
        with Timer() as timer:
            entries = client.get_entries(from_datetime=_to_datetime(day), to_datetime=_to_datetime(next_day))
        _logger.info(f"Got {len(entries)} for {day} time_took={timer.elapsed}")
        if not entries:
            return True
        store = BugoutDataStore.from_django_settings()
        store.save_data_for_day(journal_id=journal_id, day=day, bugout_data=entries)
        return True

    def on_reschedule(self, work_unit_payload: DownloadBugoutDataForDay) -> datetime.datetime:
        return utcnow() + datetime.timedelta(hours=2, minutes=10)
