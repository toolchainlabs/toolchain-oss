# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json

import pytest

from toolchain.oss_metrics.bugout_integration.data_store import BugoutDataStore
from toolchain.oss_metrics.bugout_integration.data_store_test import load_fixture
from toolchain.oss_metrics.metrics_store import AnonymousTelemetryMetricStore, RepoStatsMetricStore
from toolchain.oss_metrics.records import (
    ReferralPath,
    ReferralSource,
    RepoDailyView,
    RepoInfoStats,
    RepoReferralPaths,
    RepoReferralSources,
    RepoViews,
)
from toolchain.util.influxdb.mock_metrics_store import assert_write_request, mock_rest_client


class TestAnonymousTelemetryMetricStore:
    @pytest.fixture()
    def mock_client(self):
        with mock_rest_client() as mock_client:
            yield mock_client

    def test_store_telemetry(self, mock_client) -> None:
        telemetry_points = [BugoutDataStore.create_telemetry(tp) for tp in json.loads(load_fixture("day_data_1"))]
        store = AnonymousTelemetryMetricStore.create()
        store.store_telemetry(telemetry_points)
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


class TestRepoStatsMetricStore:
    @pytest.fixture()
    def mock_client(self):
        with mock_rest_client() as mock_client:
            yield mock_client

    @pytest.fixture()
    def store(self) -> RepoStatsMetricStore:
        return RepoStatsMetricStore.create()

    def test_store_info_stats(self, mock_client, store: RepoStatsMetricStore) -> None:
        info = RepoInfoStats(
            timestamp=datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc),
            open_issues=83,
            forks=12,
            watchers=190,
            stargazers=22222,
            subscribers=3333,
            network=11111,
        )
        store.store_info_stats(info)
        request = mock_client.get_request()
        lines = assert_write_request(request, org="pants-telemetry", bucket="repo-metrics")
        assert lines == [
            "open_issues val=83i 1641161590000000000",
            "forks val=12i 1641161590000000000",
            "watchers val=190i 1641161590000000000",
            "stargazers val=22222i 1641161590000000000",
            "subscribers val=3333i 1641161590000000000",
            "network val=11111i 1641161590000000000",
        ]

    def test_store_views(self, mock_client, store: RepoStatsMetricStore) -> None:
        views = RepoDailyView(
            day=datetime.date(2021, 7, 29),
            count=1111,
            uniques=8888,
            views=(
                RepoViews(
                    timestamp=datetime.datetime(2021, 7, 29, 2, 18, 0, tzinfo=datetime.timezone.utc),
                    count=777,
                    uniques=2222,
                ),
                RepoViews(
                    timestamp=datetime.datetime(2021, 7, 29, 2, 5, 0, tzinfo=datetime.timezone.utc),
                    count=4444,
                    uniques=8888,
                ),
            ),
        )
        store.store_views(views)
        request = mock_client.get_request()
        lines = assert_write_request(request, org="pants-telemetry", bucket="repo-metrics")
        assert lines == [
            "view_count val=777i 1627525080000000000",
            "view_uniques val=2222i 1627525080000000000",
            "view_count val=4444i 1627524300000000000",
            "view_uniques val=8888i 1627524300000000000",
        ]

    def test_store_referral_sources(self, mock_client, store: RepoStatsMetricStore) -> None:
        ref_sources = RepoReferralSources(
            timestamp=datetime.datetime(2022, 1, 2, 22, 13, 10, tzinfo=datetime.timezone.utc),
            referrers=(
                ReferralSource(referrer="nbc.com", count=9999, uniques=27271),
                ReferralSource(referrer="seinfeld.com", count=1111, uniques=5544),
            ),
        )
        store.store_referral_sources(ref_sources)
        request = mock_client.get_request()
        lines = assert_write_request(request, org="pants-telemetry", bucket="repo-metrics")
        assert lines == [
            'referral_source_count referrer="nbc.com",val=9999i 1641161590000000000',
            'referral_source_uniques referrer="nbc.com",val=27271i 1641161590000000000',
            'referral_source_count referrer="seinfeld.com",val=1111i 1641161590000000000',
            'referral_source_uniques referrer="seinfeld.com",val=5544i 1641161590000000000',
        ]

    def test_store_referral_paths(self, mock_client, store: RepoStatsMetricStore) -> None:
        ref_paths = RepoReferralPaths(
            timestamp=datetime.datetime(2021, 8, 3, 22, 13, 10, tzinfo=datetime.timezone.utc),
            referrers=(
                ReferralPath(path="festivus", title="Feats for stenth", count=8899, uniques=1999),
                ReferralPath(path="frank", title="I'm back baby", count=20201, uniques=33331),
            ),
        )
        store.store_referral_paths(ref_paths)
        request = mock_client.get_request()
        lines = assert_write_request(request, org="pants-telemetry", bucket="repo-metrics")
        assert lines == [
            'referral_source_count path="festivus",val=8899i 1628028790000000000',
            'referral_source_uniques path="festivus",val=1999i 1628028790000000000',
            'referral_source_count path="frank",val=20201i 1628028790000000000',
            'referral_source_uniques path="frank",val=33331i 1628028790000000000',
        ]
