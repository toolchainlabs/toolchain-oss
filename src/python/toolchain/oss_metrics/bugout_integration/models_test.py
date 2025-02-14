# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay, ScheduleBugoutDataDownload
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.work_dispatcher_test import mark_work_unit_success


@pytest.mark.django_db()
class TestScheduleBugoutDataDownload:
    def test_create_new(self) -> None:
        assert ScheduleBugoutDataDownload.objects.count() == 0
        pct = ScheduleBugoutDataDownload.update_or_create(88, journal_id="jerry")
        assert ScheduleBugoutDataDownload.objects.count() == 1
        loaded = ScheduleBugoutDataDownload.objects.first()
        assert loaded.period_minutes == 88
        assert loaded.journal_id == "jerry"
        assert loaded == pct

    def test_update_existing(self) -> None:
        assert ScheduleBugoutDataDownload.objects.count() == 0
        ScheduleBugoutDataDownload.update_or_create(88, journal_id="newman")
        assert ScheduleBugoutDataDownload.objects.count() == 1
        pct = ScheduleBugoutDataDownload.update_or_create(660, journal_id="newman")
        assert ScheduleBugoutDataDownload.objects.count() == 1
        loaded = ScheduleBugoutDataDownload.objects.first()
        assert loaded.period_minutes == 660
        assert loaded.journal_id == "newman"
        assert loaded == pct


@pytest.mark.django_db()
class TestDownloadBugoutDataForDay:
    def test_run_for_date_new(self) -> None:
        dl = DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 8, 25), journal_id="george")
        assert dl.day == datetime.date(2021, 8, 25)
        assert DownloadBugoutDataForDay.objects.count() == 1
        assert DownloadBugoutDataForDay.objects.first() == dl

    def test_run_for_date_existing(self) -> None:
        DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 3, 15), journal_id="george")
        DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 3, 15), journal_id="george")
        assert DownloadBugoutDataForDay.objects.count() == 1
        dl = DownloadBugoutDataForDay.objects.first()
        assert dl.day == datetime.date(2021, 3, 15)
        assert dl.journal_id == "george"
        assert dl.work_unit.state == WorkUnit.READY

    def test_run_for_date_existing_re_run(self) -> None:
        dl = DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 9, 22), journal_id="george")
        mark_work_unit_success(dl)
        assert DownloadBugoutDataForDay.objects.first().work_unit.state == WorkUnit.SUCCEEDED
        DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 9, 22), journal_id="george")
        assert DownloadBugoutDataForDay.objects.count() == 1
        dl = DownloadBugoutDataForDay.objects.first()
        assert dl.work_unit.state == WorkUnit.READY
        assert dl.day == datetime.date(2021, 9, 22)

    def test_get_latest_day_or_none(self) -> None:
        assert DownloadBugoutDataForDay.get_latest_day_or_none(journal_id="george") is None
        DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 3, 11), journal_id="george")
        DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 3, 15), journal_id="george")
        DownloadBugoutDataForDay.run_for_date(datetime.date(2021, 2, 26), journal_id="george")
        assert DownloadBugoutDataForDay.objects.count() == 3
        assert DownloadBugoutDataForDay.get_latest_day_or_none("george") == datetime.date(2021, 3, 15)
