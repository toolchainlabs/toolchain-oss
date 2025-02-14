# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.github_integration.test_utils.fixtures_loader import load_fixture
from toolchain.oss_metrics.github_data_store import GithubStatsRawStore


def add_fake_stats_fixture(bucket: str, timestamp: datetime.datetime, data_name: str, fixture_name: str) -> None:
    data = load_fixture(fixture_name)
    S3().upload_json_str(
        bucket=bucket,
        key=f"no-bagel/yamahama/hnh/bagels/{timestamp.isoformat()}/{data_name}.json",
        json_str=json.dumps(data),
    )


class TestGithubStatsRawStore:
    _BUCKET = "festivus-scm-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def data_store(self) -> GithubStatsRawStore:
        return GithubStatsRawStore.from_customer_and_repo_id(customer_id="hnh", repo_id="bagels")

    def test_get_repo_stats(self, data_store: GithubStatsRawStore) -> None:
        add_fake_stats_fixture(
            bucket=self._BUCKET,
            timestamp=datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc),
            data_name="repo_info",
            fixture_name="github_api_repo",
        )
        repo_info_stats = data_store.get_repo_stats(datetime.date(2022, 1, 2))
        assert repo_info_stats is not None
        assert repo_info_stats.timestamp == datetime.datetime(2020, 12, 16, 18, 59, 29, tzinfo=datetime.timezone.utc)
        assert repo_info_stats.open_issues == 305
        assert repo_info_stats.forks == 378
        assert repo_info_stats.watchers == 1459
        assert repo_info_stats.stargazers == 1459
        assert repo_info_stats.subscribers == 60
        assert repo_info_stats.network == 378

    def test_get_repo_referral_sources(self, data_store: GithubStatsRawStore) -> None:
        add_fake_stats_fixture(
            bucket=self._BUCKET,
            timestamp=datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc),
            data_name="repo_referral_sources",
            fixture_name="github_api_referrers",
        )
        referral_sources = data_store.get_referral_sources(datetime.date(2022, 1, 2))
        assert referral_sources is not None
        assert referral_sources.timestamp == datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc)
        assert len(referral_sources.referrers) == 10
        refr = referral_sources.referrers[4]
        assert refr.referrer == "pypi.org"
        assert refr.count == 16
        assert refr.uniques == 12

    def test_get_repo_views(self, data_store: GithubStatsRawStore) -> None:
        add_fake_stats_fixture(
            bucket=self._BUCKET,
            timestamp=datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc),
            data_name="repo_views",
            fixture_name="github_api_views",
        )
        repo_views = data_store.get_views(datetime.date(2022, 1, 2))
        assert repo_views is not None
        assert repo_views.count == 4838
        assert repo_views.uniques == 783
        assert len(repo_views.views) == 14
        view = repo_views.views[9]
        assert view.timestamp == datetime.datetime(2020, 12, 12, 0, 0, tzinfo=datetime.timezone.utc)
        assert view.count == 61
        assert view.uniques == 25

    def test_get_referral_paths(self, data_store: GithubStatsRawStore) -> None:
        add_fake_stats_fixture(
            bucket=self._BUCKET,
            timestamp=datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc),
            data_name="repo_referral_paths",
            fixture_name="github_api_paths",
        )
        ref_paths = data_store.get_referral_paths(datetime.date(2022, 1, 2))
        assert ref_paths is not None
        assert ref_paths.timestamp == datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc)
        assert len(ref_paths.referrers) == 10
        ref_path = ref_paths.referrers[6]
        assert ref_path.path == "/pantsbuild/pants/issues/11305"
        assert ref_path.title == "Trying to run pants 1.29.0 on Mac OS X Big Sur · Issue #11305 · pantsbuild/pa..."
        assert ref_path.count == 52
        assert ref_path.uniques == 16
