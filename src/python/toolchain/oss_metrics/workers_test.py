# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time
from moto import mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.oss_metrics.bugout_integration.data_store_test import add_fake_bugout_data, add_fake_bugout_fixture_data
from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay
from toolchain.oss_metrics.dispatcher import OssMetricsWorkflowDispatcher
from toolchain.oss_metrics.github_data_store_test import add_fake_stats_fixture
from toolchain.oss_metrics.models import (
    ScheduleAnonymouseTelemetryProcessing,
    ScheduleUpsertGithubRepoStats,
    UpsertGithubRepoStatsForDay,
    UpsertPantsTelemetryForDay,
)
from toolchain.oss_metrics.workers import AnonymouseTelemetryProcessingScheduler
from toolchain.util.influxdb.mock_metrics_store import assert_write_request, assert_write_requests, mock_rest_client
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests
from toolchain.workflow.work_dispatcher import WorkDispatcher
from toolchain.workflow.work_dispatcher_test import mark_work_unit_success


class BaseWorkerTests(BaseWorkflowWorkerTests):
    def get_dispatcher(self) -> type[WorkDispatcher]:
        return OssMetricsWorkflowDispatcher

    @pytest.fixture()
    def mock_client(self):
        with mock_rest_client(allow_multiple_responses=True) as mock_client:
            yield mock_client


class TestPantsTelemetryDataLoader(BaseWorkerTests):
    _BUCKET = "festivus-bugout-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def test_run_for_day(self, mock_client) -> None:
        day = datetime.date(2022, 2, 5)
        add_fake_bugout_fixture_data(
            bucket=self._BUCKET,
            journal_id="festivus",
            day=day,
            fixture_name="day_data_1",
        )
        UpsertPantsTelemetryForDay.run_for_date(day=day, journal_id="festivus")
        assert self.do_work() == 1
        wu = UpsertPantsTelemetryForDay.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        request = mock_client.get_request()
        lines = assert_write_request(request, org="pants-telemetry", bucket="anonymous-telemetry")
        assert lines == [
            'duration arch="x86_64",os="Linux",outcome="SUCCESS",pants_version="2.9.0rc0",platform="Linux-5.11.0-1022-aws-x86_64-with-glibc2.2.5",python_implementation="CPython",python_version="3.8.12",val=8.70499324798584 1641166479220967000',
            'duration arch="x86_64",os="Linux",outcome="SUCCESS",pants_version="2.9.0rc0",platform="Linux-5.10.76-linuxkit-x86_64-with-glibc2.2.5",python_implementation="CPython",python_version="3.8.12",val=20.71903395652771 1641166330839421000',
            'duration arch="x86_64",os="Linux",outcome="SUCCESS",pants_version="2.9.0rc0",platform="Linux-5.10.76-linuxkit-x86_64-with-glibc2.2.5",python_implementation="CPython",python_version="3.8.12",val=20.510681629180908 1641166299147956000',
            'num_goals arch="x86_64",os="Linux",outcome="SUCCESS",pants_version="2.9.0rc0",platform="Linux-5.11.0-1022-aws-x86_64-with-glibc2.2.5",python_implementation="CPython",python_version="3.8.12",val=1i 1641166479220967000',
            'num_goals arch="x86_64",os="Linux",outcome="SUCCESS",pants_version="2.9.0rc0",platform="Linux-5.10.76-linuxkit-x86_64-with-glibc2.2.5",python_implementation="CPython",python_version="3.8.12",val=1i 1641166330839421000',
            'num_goals arch="x86_64",os="Linux",outcome="SUCCESS",pants_version="2.9.0rc0",platform="Linux-5.10.76-linuxkit-x86_64-with-glibc2.2.5",python_implementation="CPython",python_version="3.8.12",val=1i 1641166299147956000',
            'uniques repo="93651e60079b070911a5573b3e8c02e1203658d9eaf6bc8b7dc0d225563db6c5",user="6263e7cafaf59bb0ab01ea49c1955b6025eaa3f77a8bb62a055042f2d63c4a02" 1641166479220967000',
            'uniques repo="93651e60079b070911a5573b3e8c02e1203658d9eaf6bc8b7dc0d225563db6c5",user="6263e7cafaf59bb0ab01ea49c1955b6025eaa3f77a8bb62a055042f2d63c4a02" 1641166330839421000',
            'uniques repo="93651e60079b070911a5573b3e8c02e1203658d9eaf6bc8b7dc0d225563db6c5",user="6263e7cafaf59bb0ab01ea49c1955b6025eaa3f77a8bb62a055042f2d63c4a02" 1641166299147956000',
        ]

    def test_run_for_day_no_data(self, mock_client) -> None:
        UpsertPantsTelemetryForDay.run_for_date(day=datetime.date(2022, 2, 3), journal_id="festivus")
        assert self.do_work() == 1
        mock_client.assert_no_requests()
        wu = UpsertPantsTelemetryForDay.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

    def test_upsert_with_no_duration(self, mock_client) -> None:
        day = datetime.date(2022, 2, 10)
        add_fake_bugout_fixture_data(
            bucket=self._BUCKET,
            journal_id="festivus",
            day=day,
            fixture_name="data_no_duration",
        )
        UpsertPantsTelemetryForDay.run_for_date(day=day, journal_id="festivus")
        assert self.do_work() == 1
        wu = UpsertPantsTelemetryForDay.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        request = mock_client.get_request()
        lines = assert_write_request(request, org="pants-telemetry", bucket="anonymous-telemetry")
        assert lines == [
            'num_goals arch="x86_64",os="Darwin",pants_version="2.8.0.dev2",platform="Darwin-20.6.0-x86_64-i386-64bit",python_implementation="CPython",python_version="3.7.7",val=1i 1633213991175005000',
            'uniques repo="5a01f053c895c2078d9a3db0496d8944fda894ec5f43a4f5df0023bc927e8fb5",user="81f6665e4d19e97e07ef0c9f0427a6debc96b182fe6e1387a3738939a0274925" 1633213991175005000',
        ]


class TestGithubStatsDataLoader(BaseWorkerTests):
    _BUCKET = "festivus-scm-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def test_run_for_day(self, mock_client) -> None:
        ts = datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc)
        add_fake_stats_fixture(bucket=self._BUCKET, timestamp=ts, data_name="repo_info", fixture_name="github_api_repo")
        add_fake_stats_fixture(self._BUCKET, ts, "repo_referral_sources", fixture_name="github_api_referrers")
        add_fake_stats_fixture(self._BUCKET, ts, "repo_views", fixture_name="github_api_views")
        add_fake_stats_fixture(self._BUCKET, ts, "repo_referral_paths", fixture_name="github_api_paths")
        UpsertGithubRepoStatsForDay.run_for_date(day=ts.date(), customer_id="hnh", repo_id="bagels")
        assert self.do_work() == 1
        wu = UpsertGithubRepoStatsForDay.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        reqs = mock_client.get_requests()
        assert len(reqs) == 4
        all_lines = assert_write_requests(reqs, org="pants-telemetry", bucket="repo-metrics")
        assert len(all_lines) == 74


class TestGithubRepoStatsUpsertScheduler(BaseWorkerTests):
    @freeze_time(datetime.datetime(2021, 1, 9, 0, 52, 11, tzinfo=datetime.timezone.utc))
    def test_no_previous_upserts(self) -> None:
        ScheduleUpsertGithubRepoStats.objects.create(customer_id="george", repo_id="costanza")
        assert self.do_work() == 1
        schedule_wu = ScheduleUpsertGithubRepoStats.objects.first().work_unit
        assert schedule_wu.state == WorkUnit.PENDING
        assert schedule_wu.num_unsatisfied_requirements == 6
        assert UpsertGithubRepoStatsForDay.objects.count() == 6
        upserts = list(UpsertGithubRepoStatsForDay.objects.all())
        assert {upsert.repo_id for upsert in upserts} == {"costanza"}
        assert {upsert.customer_id for upsert in upserts} == {"george"}
        today = utcnow().date()
        expected_days = {today - datetime.timedelta(days=2 + i) for i in range(6)}
        assert {upsert.day for upsert in upserts} == expected_days

    def test_with_previous_upserts(self) -> None:
        ScheduleUpsertGithubRepoStats.objects.create(customer_id="george", repo_id="costanza")
        today = utcnow().replace(hour=3).date()
        bd = today - datetime.timedelta(10)
        upsert = UpsertGithubRepoStatsForDay.run_for_date(day=bd, customer_id="george", repo_id="costanza")
        mark_work_unit_success(upsert)
        assert self.do_work() == 1
        schedule_wu = ScheduleUpsertGithubRepoStats.objects.first().work_unit
        assert schedule_wu.state == WorkUnit.PENDING
        assert schedule_wu.num_unsatisfied_requirements == 8
        assert UpsertGithubRepoStatsForDay.objects.count() == 9
        upserts = [wu.payload for wu in schedule_wu.requirements.all()]
        assert len(upserts) == 8
        assert {upsert.repo_id for upsert in upserts} == {"costanza"}
        assert {upsert.customer_id for upsert in upserts} == {"george"}
        expected_days = {today - datetime.timedelta(days=2 + i) for i in range(8)}
        assert {upsert.day for upsert in upserts} == expected_days


class TestAnonymouseTelemetryProcessingScheduler(BaseWorkerTests):
    _BUCKET = "festivus-bugout-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def test_no_op_run_once(self):
        bd = (utcnow() - datetime.timedelta(days=3)).date()
        add_fake_bugout_data(self._BUCKET, journal_id="kenny-rogers", count=3, base_date=bd)
        ScheduleAnonymouseTelemetryProcessing.update_or_create(journal_id="kenny-rogers", period_minutes=None)
        assert self.do_work() == 1
        schedule_download_work_unit = ScheduleAnonymouseTelemetryProcessing.objects.first().work_unit
        assert schedule_download_work_unit.state == WorkUnit.SUCCEEDED
        assert DownloadBugoutDataForDay.objects.count() == 0

    def test_no_op_periodic(self):
        bd = (utcnow() - datetime.timedelta(days=3)).date()
        add_fake_bugout_data(self._BUCKET, journal_id="kenny-rogers", count=4, base_date=bd)
        ScheduleAnonymouseTelemetryProcessing.update_or_create(journal_id="kenny-rogers", period_minutes=90)
        assert self.do_work() == 1
        schedule_download_work_unit = ScheduleAnonymouseTelemetryProcessing.objects.first().work_unit
        assert schedule_download_work_unit.state == WorkUnit.LEASED
        assert schedule_download_work_unit.num_unsatisfied_requirements == 0
        assert DownloadBugoutDataForDay.objects.count() == 0

    def test_queue_downloads_one_batch_periodic(self):
        bd = (utcnow() - datetime.timedelta(days=10)).date()
        add_fake_bugout_data(self._BUCKET, journal_id="kenny-rogers", count=7, base_date=bd)
        ScheduleAnonymouseTelemetryProcessing.update_or_create(journal_id="kenny-rogers", period_minutes=90)
        assert self.do_work() == 1
        schedule_download_work_unit = ScheduleAnonymouseTelemetryProcessing.objects.first().work_unit
        assert schedule_download_work_unit.state == WorkUnit.PENDING
        assert schedule_download_work_unit.num_unsatisfied_requirements == 3
        assert DownloadBugoutDataForDay.objects.count() == 3
        assert UpsertPantsTelemetryForDay.objects.count() == 3
        upserts = list(UpsertPantsTelemetryForDay.objects.all())
        assert {upsert.work_unit.num_unsatisfied_requirements for upsert in upserts} == {1}
        downloads = list(DownloadBugoutDataForDay.objects.all())
        assert {dl.journal_id for dl in downloads} == {"kenny-rogers"}
        expected_days = {bd + datetime.timedelta(days=i) for i in range(7, 10)}
        assert {dl.day for dl in downloads} == expected_days

    def test_queue_downloads_one_batch_exceed(self):
        bd = (utcnow() - datetime.timedelta(days=200)).date()
        add_fake_bugout_data(self._BUCKET, journal_id="kenny-rogers", count=7, base_date=bd)
        ScheduleAnonymouseTelemetryProcessing.update_or_create(journal_id="kenny-rogers", period_minutes=90)
        assert self.do_work() == 1
        schedule_download_work_unit = ScheduleAnonymouseTelemetryProcessing.objects.first().work_unit
        assert schedule_download_work_unit.state == WorkUnit.PENDING
        assert schedule_download_work_unit.num_unsatisfied_requirements == 20
        assert DownloadBugoutDataForDay.objects.count() == 20 == AnonymouseTelemetryProcessingScheduler.MAX_BATCH_SIZE
        assert UpsertPantsTelemetryForDay.objects.count() == 20
        upserts = list(UpsertPantsTelemetryForDay.objects.all())
        assert {upsert.work_unit.num_unsatisfied_requirements for upsert in upserts} == {1}
        downloads = list(DownloadBugoutDataForDay.objects.all())
        assert {dl.journal_id for dl in downloads} == {"kenny-rogers"}
        expected_days = {bd + datetime.timedelta(days=i) for i in range(7, 27)}
        assert {dl.day for dl in downloads} == expected_days

    def test_queue_downloads_no_data(self):
        ScheduleAnonymouseTelemetryProcessing.update_or_create(journal_id="kenny-rogers", period_minutes=800)
        assert self.do_work() == 1
        schedule_download_work_unit = ScheduleAnonymouseTelemetryProcessing.objects.first().work_unit
        assert schedule_download_work_unit.state == WorkUnit.PENDING
        assert schedule_download_work_unit.num_unsatisfied_requirements == 20
        assert DownloadBugoutDataForDay.objects.count() == 20
        assert UpsertPantsTelemetryForDay.objects.count() == 20
        upserts = list(UpsertPantsTelemetryForDay.objects.all())
        assert {upsert.work_unit.num_unsatisfied_requirements for upsert in upserts} == {1}
        downloads = list(DownloadBugoutDataForDay.objects.all())
        assert {dl.journal_id for dl in downloads} == {"kenny-rogers"}
        bd = datetime.date(2021, 3, 15)
        expected_days = {bd + datetime.timedelta(days=i) for i in range(20)}
        assert {dl.day for dl in downloads} == expected_days

    def test_queue_downloads_with_existing_queued_downloads(self):
        bd = (utcnow() - datetime.timedelta(days=45)).date()
        add_fake_bugout_data(self._BUCKET, journal_id="Kramerica", count=30, base_date=bd)
        DownloadBugoutDataForDay.run_for_date(day=bd + datetime.timedelta(days=31), journal_id="Kramerica")
        DownloadBugoutDataForDay.run_for_date(day=bd + datetime.timedelta(days=32), journal_id="Kramerica")
        DownloadBugoutDataForDay.run_for_date(day=bd + datetime.timedelta(days=33), journal_id="Kramerica")
        for dl in DownloadBugoutDataForDay.objects.all():
            mark_work_unit_success(dl)
        ScheduleAnonymouseTelemetryProcessing.update_or_create(journal_id="Kramerica", period_minutes=90)
        assert self.do_work() == 1
        schedule_download_work_unit = ScheduleAnonymouseTelemetryProcessing.objects.first().work_unit
        assert schedule_download_work_unit.state == WorkUnit.PENDING
        assert schedule_download_work_unit.num_unsatisfied_requirements == 11 == (45 - 30 - 3 - 1)
        assert DownloadBugoutDataForDay.objects.count() == 11 + 3
        assert UpsertPantsTelemetryForDay.objects.count() == 11
        downloads = list(DownloadBugoutDataForDay.objects.all())
        upserts = list(UpsertPantsTelemetryForDay.objects.all())
        assert {upsert.work_unit.num_unsatisfied_requirements for upsert in upserts} == {1}
        assert {dl.journal_id for dl in downloads} == {"Kramerica"}
        expected_days = {bd + datetime.timedelta(days=i) for i in range(31, 45)}
        assert {dl.day for dl in downloads} == expected_days
