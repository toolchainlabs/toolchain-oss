# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.oss_metrics.models import (
    ScheduleAnonymouseTelemetryProcessing,
    UpsertGithubRepoStatsForDay,
    UpsertPantsTelemetryForDay,
)
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.work_dispatcher_test import mark_work_unit_success


@pytest.mark.django_db()
class TestUpsertPantsTelemetryForDay:
    def test_run_for_date_new(self) -> None:
        dl = UpsertPantsTelemetryForDay.run_for_date(datetime.date(2021, 8, 25), journal_id="george")
        assert dl.day == datetime.date(2021, 8, 25)
        assert UpsertPantsTelemetryForDay.objects.count() == 1
        assert UpsertPantsTelemetryForDay.objects.first() == dl

    def test_run_for_date_existing(self) -> None:
        UpsertPantsTelemetryForDay.run_for_date(datetime.date(2021, 3, 15), journal_id="george")
        UpsertPantsTelemetryForDay.run_for_date(datetime.date(2021, 3, 15), journal_id="george")
        assert UpsertPantsTelemetryForDay.objects.count() == 1
        dl = UpsertPantsTelemetryForDay.objects.first()
        assert dl.day == datetime.date(2021, 3, 15)
        assert dl.journal_id == "george"
        assert dl.work_unit.state == WorkUnit.READY

    def test_run_for_date_existing_re_run(self) -> None:
        upsert = UpsertPantsTelemetryForDay.run_for_date(datetime.date(2021, 9, 22), journal_id="george")
        mark_work_unit_success(upsert)
        assert UpsertPantsTelemetryForDay.objects.first().work_unit.state == WorkUnit.SUCCEEDED
        UpsertPantsTelemetryForDay.run_for_date(datetime.date(2021, 9, 22), journal_id="george")
        assert UpsertPantsTelemetryForDay.objects.count() == 1
        dl = UpsertPantsTelemetryForDay.objects.first()
        assert dl.work_unit.state == WorkUnit.READY
        assert dl.day == datetime.date(2021, 9, 22)


@pytest.mark.django_db()
class TestUpsertGithubRepoStatsForDay:
    def test_run_for_date_new(self) -> None:
        ghupsert = UpsertGithubRepoStatsForDay.run_for_date(
            datetime.date(2021, 8, 25), customer_id="george", repo_id="costanza"
        )
        assert ghupsert.day == datetime.date(2021, 8, 25)
        assert UpsertGithubRepoStatsForDay.objects.count() == 1
        assert UpsertGithubRepoStatsForDay.objects.first() == ghupsert

    def test_run_for_date_existing(self) -> None:
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 3, 15), customer_id="george", repo_id="costanza")
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 3, 15), customer_id="george", repo_id="costanza")
        assert UpsertGithubRepoStatsForDay.objects.count() == 1
        ghupsert = UpsertGithubRepoStatsForDay.objects.first()
        assert ghupsert.day == datetime.date(2021, 3, 15)
        assert ghupsert.customer_id == "george"
        assert ghupsert.repo_id == "costanza"
        assert ghupsert.work_unit.state == WorkUnit.READY

    def test_run_for_date_existing_re_run(self) -> None:
        upsert = UpsertGithubRepoStatsForDay.run_for_date(
            datetime.date(2021, 9, 22), customer_id="george", repo_id="costanza"
        )
        mark_work_unit_success(upsert)
        assert UpsertGithubRepoStatsForDay.objects.first().work_unit.state == WorkUnit.SUCCEEDED
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 9, 22), customer_id="george", repo_id="costanza")
        assert UpsertGithubRepoStatsForDay.objects.count() == 1
        ghupsert = UpsertGithubRepoStatsForDay.objects.first()
        assert ghupsert.work_unit.state == WorkUnit.READY
        assert ghupsert.day == datetime.date(2021, 9, 22)

    def test_get_latest_day_or_none(self) -> None:
        assert UpsertGithubRepoStatsForDay.get_latest_day_or_none(customer_id="george", repo_id="costanza") is None
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 3, 11), customer_id="george", repo_id="costanza")
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 3, 15), customer_id="george", repo_id="costanza")
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 2, 26), customer_id="george", repo_id="costanza")
        UpsertGithubRepoStatsForDay.run_for_date(datetime.date(2021, 5, 26), customer_id="george", repo_id="buck")
        assert UpsertGithubRepoStatsForDay.objects.count() == 4
        assert UpsertGithubRepoStatsForDay.get_latest_day_or_none(
            customer_id="george", repo_id="costanza"
        ) == datetime.date(2021, 3, 15)


@pytest.mark.django_db()
class TestScheduleAnonymouseTelemetryProcessing:
    def test_create_new(self) -> None:
        assert ScheduleAnonymouseTelemetryProcessing.objects.count() == 0
        pct = ScheduleAnonymouseTelemetryProcessing.update_or_create(88, journal_id="jerry")
        assert ScheduleAnonymouseTelemetryProcessing.objects.count() == 1
        loaded = ScheduleAnonymouseTelemetryProcessing.objects.first()
        assert loaded.period_minutes == 88
        assert loaded.journal_id == "jerry"
        assert loaded == pct

    def test_update_existing(self) -> None:
        assert ScheduleAnonymouseTelemetryProcessing.objects.count() == 0
        ScheduleAnonymouseTelemetryProcessing.update_or_create(88, journal_id="newman")
        assert ScheduleAnonymouseTelemetryProcessing.objects.count() == 1
        pct = ScheduleAnonymouseTelemetryProcessing.update_or_create(660, journal_id="newman")
        assert ScheduleAnonymouseTelemetryProcessing.objects.count() == 1
        loaded = ScheduleAnonymouseTelemetryProcessing.objects.first()
        assert loaded.period_minutes == 660
        assert loaded.journal_id == "newman"
        assert loaded == pct
