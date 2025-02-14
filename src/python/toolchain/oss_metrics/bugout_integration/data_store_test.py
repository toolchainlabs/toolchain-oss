# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging

import pkg_resources
import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.oss_metrics.bugout_integration.data_store import BugoutDataStore

_logger = logging.getLogger(__name__)


def load_fixture(fixture_name: str) -> str:
    return pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json").decode()


def add_fake_bugout_fixture_data(bucket: str, journal_id: str, day: datetime.date, fixture_name: str) -> None:
    data = load_fixture(fixture_name)
    S3().upload_json_str(
        bucket=bucket,
        key=f"european/carry-all/festivus/{day.year}/{day.isoformat()}.json",
        json_str=data,
    )


def add_fake_bugout_data(bucket: str, journal_id: str, count: int, base_date: datetime.date | None = None) -> None:
    s3 = S3()
    data = json.dumps([{"bob": "sacamano"}, {"elaine": "benes"}])
    bd = base_date or datetime.date(year=2021, month=7, day=8)
    for i in range(count):
        dt = bd + datetime.timedelta(days=i)
        key = f"european/carry-all/{journal_id}/{dt.year}/{dt.isoformat()}.json"
        _logger.info(f"Add fake bugout data at {key=}")
        s3.upload_json_str(bucket=bucket, key=key, json_str=data)


class TestBugoutDataStore:
    _BUCKET = "festivus-bugout-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def data_store(self) -> BugoutDataStore:
        return BugoutDataStore.from_django_settings()

    def test_save_data_for_day(self, data_store: BugoutDataStore) -> None:
        assert_bucket_empty(S3(), bucket_name=self._BUCKET)
        data_store.save_data_for_day(
            journal_id="uncle-leo", day=datetime.date(2021, 12, 23), bugout_data=[{"jerry": "Uncle Leo"}]
        )
        data, key_info = S3().get_content_with_object(
            bucket=self._BUCKET, key="european/carry-all/uncle-leo/2021/2021-12-23.json"
        )
        assert json.loads(data) == [{"jerry": "Uncle Leo"}]
        assert key_info.content_type == "application/json"
        assert not key_info.metadata
        assert key_info.length == 24

    def test_save_data_for_day_empty(self, data_store: BugoutDataStore) -> None:
        with pytest.raises(ToolchainAssertion, match="No data/empty data for"):
            data_store.save_data_for_day(
                journal_id="vandelay-industries", day=datetime.date(2021, 11, 7), bugout_data=[]
            )
        assert_bucket_empty(S3(), bucket_name=self._BUCKET)

    def test_get_latest_data_date_empty(self, data_store: BugoutDataStore) -> None:
        assert_bucket_empty(S3(), bucket_name=self._BUCKET)
        assert data_store.get_latest_data_date("vandelay-industries") == datetime.date(2021, 3, 14)

    def _add_data(self, journal_id: str, year: int, count: int) -> None:
        add_fake_bugout_data(
            bucket=self._BUCKET, journal_id=journal_id, count=count, base_date=datetime.date(year=year, month=7, day=8)
        )

    def test_get_latest_data_single_year(self, data_store: BugoutDataStore) -> None:
        assert_bucket_empty(S3(), bucket_name=self._BUCKET)
        self._add_data("vandelay-industries", 2021, count=35)
        assert data_store.get_latest_data_date("vandelay-industries") == datetime.date(2021, 8, 11)

    def test_get_latest_data_multiple_years(self, data_store: BugoutDataStore) -> None:
        assert_bucket_empty(S3(), bucket_name=self._BUCKET)
        self._add_data("yada-yada", 2022, count=17)
        self._add_data("yada-yada", 2023, count=29)
        self._add_data("yada-yada", 2019, count=6)
        self._add_data("yada-yada", 2021, count=8)
        assert data_store.get_latest_data_date("yada-yada") == datetime.date(2023, 8, 5)

    def test_get_data_for_day(self, data_store: BugoutDataStore) -> None:
        add_fake_bugout_fixture_data(
            bucket=self._BUCKET,
            journal_id="festivus",
            day=datetime.date(2022, 1, 2),
            fixture_name="day_data_1",
        )
        telemetry_data = data_store.get_data_for_day("festivus", datetime.date(2022, 1, 2))
        assert telemetry_data is not None
        assert len(telemetry_data) == 3
        tm = telemetry_data[1]
        assert tm.timestamp == datetime.datetime(2022, 1, 2, 23, 32, 10, 839421, tzinfo=datetime.timezone.utc)
        assert tm.tags == {
            "outcome": "SUCCESS",
            "pants_version": "2.9.0rc0",
            "python_implementation": "CPython",
            "python_version": "3.8.12",
            "platform": "Linux-5.10.76-linuxkit-x86_64-with-glibc2.2.5",
            "os": "Linux",
            "arch": "x86_64",
        }
        assert tm.run_id == "pants_run_2022_01_02_23_32_13_442_2f88fd081a16461587b3658795f913fb"
        assert tm.repo_id == "93651e60079b070911a5573b3e8c02e1203658d9eaf6bc8b7dc0d225563db6c5"
        assert tm.user_id == "6263e7cafaf59bb0ab01ea49c1955b6025eaa3f77a8bb62a055042f2d63c4a02"
        assert tm.machine_id == "cc8e44a38ab329f503891d3e906f16c5152a171b68ae33e9718cebea95a06116"
        assert tm.standard_goals == ["package"]
        assert tm.duration == 20.71903395652771
        assert tm.num_goals == 1

    def test_get_data_no_duration(self, data_store: BugoutDataStore) -> None:
        add_fake_bugout_fixture_data(
            bucket=self._BUCKET,
            journal_id="festivus",
            day=datetime.date(2022, 2, 10),
            fixture_name="data_no_duration",
        )
        telemetry_data = data_store.get_data_for_day("festivus", datetime.date(2022, 2, 10))
        assert telemetry_data is not None
        assert len(telemetry_data) == 1
        tm = telemetry_data[0]
        assert tm.timestamp == datetime.datetime(2021, 10, 2, 22, 33, 11, 175005, tzinfo=datetime.timezone.utc)
        assert tm.tags == {
            "pants_version": "2.8.0.dev2",
            "python_implementation": "CPython",
            "python_version": "3.7.7",
            "platform": "Darwin-20.6.0-x86_64-i386-64bit",
            "os": "Darwin",
            "arch": "x86_64",
        }
        assert tm.run_id == "pants_run_2021_10_02_15_33_15_527_2f039cc88ae349e0ba309e886811b6c8"
        assert tm.repo_id == "5a01f053c895c2078d9a3db0496d8944fda894ec5f43a4f5df0023bc927e8fb5"
        assert tm.user_id == "81f6665e4d19e97e07ef0c9f0427a6debc96b182fe6e1387a3738939a0274925"
        assert tm.machine_id == "097b023dff17a92ec35caba50371cabea2007f5d01570309782e7c487c7c4dda"
        assert tm.standard_goals == ["test"]
        assert tm.duration is None
        assert tm.num_goals == 1
