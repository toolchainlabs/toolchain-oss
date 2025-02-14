# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import calendar
import datetime

import pytest
from freezegun import freeze_time
from moto import mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.oss_metrics.bugout_integration.client_test import (
    add_bugout_http_504_error_response,
    add_bugout_search_response,
    assert_bugout_request,
)
from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay
from toolchain.oss_metrics.dispatcher import OssMetricsWorkflowDispatcher
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests
from toolchain.workflow.work_dispatcher import WorkDispatcher


class BaseWorkerTests(BaseWorkflowWorkerTests):
    def get_dispatcher(self) -> type[WorkDispatcher]:
        return OssMetricsWorkflowDispatcher

    _BUCKET = "festivus-bugout-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield


class TestBugoutDayDataDownloader(BaseWorkerTests):
    def test_run_for_day(self, responses):
        add_bugout_search_response(responses, entries_count=10)
        day = datetime.date(2021, 3, 11)
        DownloadBugoutDataForDay.run_for_date(day, journal_id="shmoopi")
        assert self.do_work() == 1
        assert len(responses.calls) == 1
        from_ts = calendar.timegm(day.timetuple())
        assert_bugout_request(responses.calls[0].request, from_ts=from_ts, to_ts=from_ts + 24 * 60 * 60)
        download_wu = DownloadBugoutDataForDay.objects.first().work_unit
        assert download_wu.state == WorkUnit.SUCCEEDED

    def test_run_for_day_no_data(self, responses):
        add_bugout_search_response(responses)
        day = datetime.date(2022, 1, 16)
        DownloadBugoutDataForDay.run_for_date(day, journal_id="shmoopi")
        assert self.do_work() == 1
        assert len(responses.calls) == 1
        from_ts = calendar.timegm(day.timetuple())
        assert_bugout_request(responses.calls[0].request, from_ts=from_ts, to_ts=from_ts + 24 * 60 * 60)
        download_wu = DownloadBugoutDataForDay.objects.first().work_unit
        assert download_wu.state == WorkUnit.SUCCEEDED

    @freeze_time(datetime.datetime(2022, 1, 19, 18, 22, 0, tzinfo=datetime.timezone.utc))
    def test_run_for_yesterday_after_2am(self, responses):
        add_bugout_search_response(responses, entries_count=10)
        day = datetime.date(2022, 1, 18)
        DownloadBugoutDataForDay.run_for_date(day, journal_id="shmoopi")
        assert self.do_work() == 1
        assert len(responses.calls) == 1
        from_ts = calendar.timegm(day.timetuple())
        assert_bugout_request(responses.calls[0].request, from_ts=from_ts, to_ts=from_ts + 24 * 60 * 60)
        download_wu = DownloadBugoutDataForDay.objects.first().work_unit
        assert download_wu.state == WorkUnit.SUCCEEDED

    @freeze_time(datetime.datetime(2022, 1, 25, 1, 28, 0, tzinfo=datetime.timezone.utc))
    def test_run_for_yesterday_before_2am(self, responses):
        day = datetime.date(2022, 1, 24)
        DownloadBugoutDataForDay.run_for_date(day, journal_id="shmoopi")
        assert self.do_work() == 1
        assert len(responses.calls) == 0
        download_wu = DownloadBugoutDataForDay.objects.first().work_unit
        assert download_wu.state == WorkUnit.LEASED

    def test_run_for_day_transient_error(self, responses):
        add_bugout_http_504_error_response(responses)
        day = datetime.date(2022, 1, 16)
        DownloadBugoutDataForDay.run_for_date(day, journal_id="shmoopi")
        assert self.do_work() == 1
        assert len(responses.calls) == 1
        from_ts = calendar.timegm(day.timetuple())
        assert_bugout_request(responses.calls[0].request, from_ts=from_ts, to_ts=from_ts + 24 * 60 * 60)
        download_wu = DownloadBugoutDataForDay.objects.first().work_unit
        assert download_wu.state == WorkUnit.LEASED
