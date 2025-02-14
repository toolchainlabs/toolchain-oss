# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from toolchain.base.date_tools import get_dates_range
from toolchain.base.datetime_tools import utcnow
from toolchain.oss_metrics.bugout_integration.data_store import BugoutDataStore
from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay
from toolchain.oss_metrics.github_data_store import GithubStatsRawStore
from toolchain.oss_metrics.metrics_store import AnonymousTelemetryMetricStore, RepoStatsMetricStore
from toolchain.oss_metrics.models import (
    ScheduleAnonymouseTelemetryProcessing,
    ScheduleUpsertGithubRepoStats,
    UpsertGithubRepoStatsForDay,
    UpsertPantsTelemetryForDay,
)
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class AnonymouseTelemetryProcessingScheduler(Worker):
    work_unit_payload_cls = ScheduleAnonymouseTelemetryProcessing
    MAX_BATCH_SIZE = 20  # Don't schedule more than 20 days in a given run to avoid overwhelming the Bugout API

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._latest_data_date: datetime.date = datetime.date(2019, 1, 1)

    def do_work(self, work_unit_payload: ScheduleAnonymouseTelemetryProcessing) -> bool:
        journal_id = work_unit_payload.journal_id
        store = BugoutDataStore.from_django_settings()
        self._latest_data_date = store.get_latest_data_date(journal_id)
        latest_day_download = DownloadBugoutDataForDay.get_latest_day_or_none(journal_id=journal_id)
        if latest_day_download:
            self._latest_data_date = max(self._latest_data_date, latest_day_download)
        return work_unit_payload.period_minutes is None

    def _queue_data_download(self, journal_id: str) -> list[DownloadBugoutDataForDay]:
        max_date = utcnow() - datetime.timedelta(days=1)
        start_date = self._latest_data_date + datetime.timedelta(days=1)
        days = get_dates_range(start_date, max_date)[: self.MAX_BATCH_SIZE]
        if days:
            _logger.info(f"Queue downloading data for {len(days)} - {days[0]} - {days[-1]}")
        else:
            _logger.info(f"No downloads queued: {start_date=} {max_date=}")
        return [DownloadBugoutDataForDay.run_for_date(day=day, journal_id=journal_id) for day in days]

    def on_success(self, work_unit_payload: ScheduleAnonymouseTelemetryProcessing) -> None:
        self._queue_data_download(work_unit_payload.journal_id)

    def on_reschedule(self, work_unit_payload: ScheduleAnonymouseTelemetryProcessing) -> datetime.datetime:
        journal_id = work_unit_payload.journal_id
        downloads = self._queue_data_download(journal_id)
        for download in downloads:
            upsert = UpsertPantsTelemetryForDay.run_for_date(download.day, journal_id=journal_id)
            upsert.add_requirement_by_id(download.work_unit_id)
            work_unit_payload.add_requirement_by_id(download.work_unit_id)
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)


class PantsTelemetryDataLoader(Worker):
    work_unit_payload_cls = UpsertPantsTelemetryForDay

    def do_work(self, work_unit_payload: UpsertPantsTelemetryForDay) -> bool:
        day = work_unit_payload.day
        journal_id = work_unit_payload.journal_id
        data_store = BugoutDataStore.from_django_settings()
        telemetry_store = AnonymousTelemetryMetricStore.create()

        telemetry_data_points = data_store.get_data_for_day(journal_id=journal_id, day=day)
        if not telemetry_data_points:
            _logger.info(f"no telemetry data for {day=} {journal_id=}")
            return True
        telemetry_store.store_telemetry(telemetry_data_points)
        return True


class GithubStatsDataLoader(Worker):
    work_unit_payload_cls = UpsertGithubRepoStatsForDay

    def do_work(self, work_unit_payload: UpsertGithubRepoStatsForDay) -> bool:
        day = work_unit_payload.day
        data_store = GithubStatsRawStore.from_customer_and_repo_id(
            customer_id=work_unit_payload.customer_id, repo_id=work_unit_payload.repo_id
        )
        metric_store = RepoStatsMetricStore.create()
        added = []
        repo_stats = data_store.get_repo_stats(day)
        if repo_stats:
            metric_store.store_info_stats(repo_stats)
            added.append("info")
        views = data_store.get_views(day)
        if views:
            metric_store.store_views(views)
            added.append("views")
        ref_sources = data_store.get_referral_sources(day)
        if ref_sources:
            metric_store.store_referral_sources(ref_sources)
            added.append("referral_sources")
        ref_paths = data_store.get_referral_paths(day)
        if ref_paths:
            metric_store.store_referral_paths(ref_paths)
            added.append("referral_paths")
        _logger.info(f"Added data for {day.isoformat()} {added}")
        return True


class GithubRepoStatsUpsertScheduler(Worker):
    work_unit_payload_cls = ScheduleUpsertGithubRepoStats
    EARLIEST_DATE = datetime.date(2021, 1, 1)  # we don't have data before this date

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._days_to_schedule: tuple[datetime.date, ...] = tuple()

    def do_work(self, work_unit_payload: ScheduleUpsertGithubRepoStats) -> bool:
        latest_day = UpsertGithubRepoStatsForDay.get_latest_day_or_none(
            customer_id=work_unit_payload.customer_id, repo_id=work_unit_payload.repo_id
        )
        start_date = max(self.EARLIEST_DATE, latest_day or self.EARLIEST_DATE) + datetime.timedelta(days=1)
        self._days_to_schedule = get_dates_range(start_date, utcnow() - datetime.timedelta(days=2))
        return False

    def on_reschedule(self, work_unit_payload: ScheduleUpsertGithubRepoStats) -> datetime.datetime:
        for day in self._days_to_schedule:
            upsert = UpsertGithubRepoStatsForDay.run_for_date(
                day=day, customer_id=work_unit_payload.customer_id, repo_id=work_unit_payload.repo_id
            )
            work_unit_payload.add_requirement_by_id(upsert.work_unit_id)
        return utcnow() + datetime.timedelta(hours=12)
