# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock

import pytest
from influxdb_client.rest import ApiException
from urllib3.exceptions import NewConnectionError

from toolchain.buildsense.ingestion.metrics_store import (
    MetricsStoreTransientError,
    PantsMetricsStore,
    PantsMetricsStoreManager,
)
from toolchain.buildsense.ingestion.run_info_raw_store import BuildFile
from toolchain.buildsense.test_utils.data_loader import load_run_info
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.util.influxdb.exceptions import MissingBucketError
from toolchain.util.influxdb.mock_metrics_store import (
    assert_create_bucket_request,
    assert_get_buckets_request,
    assert_write_request,
    mock_rest_client,
)


@pytest.fixture()
def mock_client():
    with mock_rest_client() as mock_client:
        yield mock_client


@pytest.fixture()
def repo() -> Repo:
    customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
    return Repo.create("funnyguy", customer=customer, name="Jerry Seinfeld is a funny guy")


def _add_query_response(mock_client, data_lines: list[str]) -> None:
    mock_client.add_query_response(
        [
            "#group,false,false,true,true,true,true,false",
            "#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,string,string,double",
            "#default,_result,,,,,,",
            ",result,table,_start,_stop,_measurement,_field,_value",
        ]
        + data_lines
    )


def add_hit_fractions_query_response(mock_client) -> None:
    _add_query_response(
        mock_client,
        [
            ",,0,2021-04-03T12:44:50Z,2021-09-07T16:24:50.01043578Z,indicators,hit_fraction,0.7867914",
            ",,1,2021-04-03T12:44:50Z,2021-09-07T16:24:50.01043578Z,indicators,hit_fraction_local,0.8142682222222222"
            ",,2,2021-04-03T12:44:50Z,2021-09-07T16:24:50.01043578Z,indicators,hit_fraction_remote,0",
        ],
    )


def add_sums_query_response(mock_client) -> None:
    _add_query_response(
        mock_client,
        [
            ",,0,2021-04-03T12:44:50Z,2021-09-07T17:02:29.268607486Z,indicators,hits,7787",
            ",,1,2021-04-03T12:44:50Z,2021-09-07T17:02:29.268607486Z,indicators,saved_cpu_time,3373994",
            ",,2,2021-04-03T12:44:50Z,2021-09-07T17:02:29.268607486Z,indicators,saved_cpu_time_local,3258133",
            ",,3,2021-04-03T12:44:50Z,2021-09-07T17:02:29.268607486Z,indicators,saved_cpu_time_remote,0",
            ",,4,2021-04-03T12:44:50Z,2021-09-07T17:02:29.268607486Z,indicators,total,12367",
        ],
    )


@pytest.mark.django_db()
class TestPantsMetricsStoreManager:
    def test_init_bucket_exits(self, mock_client, repo: Repo) -> None:
        store = PantsMetricsStoreManager.for_repo(repo)
        mock_client.add_get_buckets_response("jerry/funnyguy")
        assert store.init_bucket(recreate=False) is False
        assert_get_buckets_request(mock_client.get_request(), "jerry/funnyguy")

    def test_init_bucket_create(self, mock_client, repo: Repo) -> None:
        store = PantsMetricsStoreManager.for_repo(repo)
        mock_client.add_get_buckets_response()
        mock_client.add_get_orgs_response()
        mock_client.add_create_bucket_response("jerry/funnyguy")
        assert store.init_bucket(recreate=False, retention_days=100) is True
        requests = mock_client.get_requests()
        assert len(requests) == 3
        assert_get_buckets_request(requests[0], "jerry/funnyguy")
        assert_create_bucket_request(requests[2], "jerry/funnyguy", retention_seconds=8640000)


@pytest.mark.django_db()
class TestPantsMetricsStore:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")

    def _get_fake_run_info(self, ts: datetime.datetime, indicators: dict | None = None):
        return MagicMock(
            ci_info=None,
            timestamp=ts,
            machine="pole",
            outcome="SUCCESS",
            branch="cosmo",
            version="mandelbaum",
            computed_goals=("davola",),
            indicators=indicators,
        )

    def _get_fake_indicators(self) -> dict[str, float | int]:
        return {
            "used_cpu_time": 160429,
            "saved_cpu_time": 373895,
            "saved_cpu_time_local": 160429,
            "saved_cpu_time_remote": 0,
            "hits": 1103,
            "total": 1178,
            "hit_fraction": 0.9363327674023769,
            "hit_fraction_local": 0.9577092511013215,
            "hit_fraction_remote": 0.37209302325581395,
        }

    def _get_metrics_file(self) -> BuildFile:
        metrics = {"cabana-shirt": 76221}
        return BuildFile(
            name="moles",
            content_type="application/json",
            content=json.dumps([{"content": metrics}]).encode(),
            metadata={},
            s3_bucket="sofa",
            s3_key="poppy",
        )

    def test_store_work_unit_metrics(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts)
        metrics_file = self._get_metrics_file()
        store.store_metrics(run_info=fake_ri, user=user, metrics_file=metrics_file)
        request = mock_client.get_request()
        lines = self._assert_write_request(request)
        assert lines == [
            f"workunits,branch=cosmo,ci=0,context=desktop,goals=davola,outcome=SUCCESS,pants_version=mandelbaum,user_api_id={user.api_id},username=elaine cabana-shirt=76221i 1617453890000000000"
        ]

    def test_store_work_unit_metrics_from_ci_run(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        run_info = load_run_info("bitbucket_pr_lint_run", repo=repo, user=user)
        metrics_file = self._get_metrics_file()
        store.store_metrics(run_info=run_info, user=user, metrics_file=metrics_file)
        request = mock_client.get_request()
        lines = self._assert_write_request(request)
        assert lines == [
            f"workunits,branch=upgrades,ci=1,context=ci_pull_request,goals=lint,outcome=SUCCESS,pants_version=2.6.0,pr=11,title=No\\ soup\\ for\\ you\\ come\\ back\\ one\\ year!,user_api_id={user.api_id},username=elaine cabana-shirt=76221i 1628640689041658000"
        ]

    def test_store_indictors_metrics(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts, indicators=self._get_fake_indicators())
        store.store_metrics(run_info=fake_ri, user=user, metrics_file=None)
        request = mock_client.get_request()
        lines = self._assert_write_request(request)

        assert lines == [
            f"indicators,branch=cosmo,ci=0,context=desktop,goals=davola,outcome=SUCCESS,pants_version=mandelbaum,user_api_id={user.api_id},username=elaine hit_fraction=0.9363327674023769,hit_fraction_local=0.9577092511013215,hit_fraction_remote=0.37209302325581395,hits=1103i,saved_cpu_time=373895i,saved_cpu_time_local=160429i,saved_cpu_time_remote=0i,total=1178i,used_cpu_time=160429i 1617453890000000000"
        ]

    def test_store_work_unit_metrics_and_indicators(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts, indicators=self._get_fake_indicators())
        metrics_file = self._get_metrics_file()
        store.store_metrics(run_info=fake_ri, user=user, metrics_file=metrics_file)
        request = mock_client.get_request()
        lines = self._assert_write_request(request)

        assert lines == [
            f"workunits,branch=cosmo,ci=0,context=desktop,goals=davola,outcome=SUCCESS,pants_version=mandelbaum,user_api_id={user.api_id},username=elaine cabana-shirt=76221i 1617453890000000000",
            f"indicators,branch=cosmo,ci=0,context=desktop,goals=davola,outcome=SUCCESS,pants_version=mandelbaum,user_api_id={user.api_id},username=elaine hit_fraction=0.9363327674023769,hit_fraction_local=0.9577092511013215,hit_fraction_remote=0.37209302325581395,hits=1103i,saved_cpu_time=373895i,saved_cpu_time_local=160429i,saved_cpu_time_remote=0i,total=1178i,used_cpu_time=160429i 1617453890000000000",
        ]

    def test_store_nothing(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts)
        store.store_metrics(run_info=fake_ri, user=user, metrics_file=None)
        mock_client.assert_no_requests()

    def _assert_write_request(self, request) -> list[str]:
        return assert_write_request(request, org="buildsense", bucket="jerry/funnyguy")

    def test_query_hit_fractions(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        add_hit_fractions_query_response(mock_client)
        start = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        result = store.query_hit_fractions(start_datetime=start, end_datetime=None, filters={})
        assert result == {"hit_fraction": 0.7867914, "hit_fraction_local": 0.8142682222222222}
        assert mock_client.get_request().json_body() == {
            "extern": {"imports": [], "body": []},
            "query": 'from(bucket: "jerry/funnyguy")\n|> range(start:2021-04-03T12:44:50Z, stop:now())\n|> filter(fn: (r) => r["_measurement"] == "indicators" and r["_field"] =~ /hit_fraction.?/)\n|> group(columns: ["_measurement", "_field"], mode:"by")\n|> mean(column: "_value")',
            "dialect": {
                "header": True,
                "delimiter": ",",
                "annotations": ["datatype", "group", "default"],
                "commentPrefix": "#",
                "dateTimeFormat": "RFC3339",
            },
        }

    def test_query_sums(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        add_sums_query_response(mock_client)
        start = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        result = store.query_sums(start_datetime=start, end_datetime=None, filters={})
        assert result == {
            "hits": 7787.0,
            "saved_cpu_time": 3373994.0,
            "saved_cpu_time_local": 3258133.0,
            "saved_cpu_time_remote": 0.0,
            "total": 12367.0,
        }
        assert mock_client.get_request().json_body() == {
            "extern": {"imports": [], "body": []},
            "query": 'from(bucket: "jerry/funnyguy")\n|> range(start:2021-04-03T12:44:50Z, stop:now())\n|> filter(fn: (r) => r["_measurement"] == "indicators" and r["_field"] =~ /saved_cpu_time.?|hits|total/)\n|> group(columns: ["_measurement", "_field"], mode:"by")\n|> sum(column: "_value")',
            "dialect": {
                "header": True,
                "delimiter": ",",
                "annotations": ["datatype", "group", "default"],
                "commentPrefix": "#",
                "dateTimeFormat": "RFC3339",
            },
        }

    def test_get_aggregated_indicators(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        store = PantsMetricsStore.for_repo(repo)
        add_sums_query_response(mock_client)
        add_hit_fractions_query_response(mock_client)
        start = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        result = store.get_aggregated_indicators(
            earliest=start,
            latest=None,
            fields_map={"ci": "0", "goals": ["david", "puddy", "newman"], "outcome": "SOUP"},
        )
        assert result == {
            "hits": 7787.0,
            "saved_cpu_time": 3373994.0,
            "saved_cpu_time_local": 3258133.0,
            "saved_cpu_time_remote": 0.0,
            "total": 12367.0,
            "hit_fraction": 0.7867914,
            "hit_fraction_local": 0.8142682222222222,
        }
        reqs = mock_client.get_requests()
        assert len(reqs) == 2
        assert reqs[0].json_body() == {
            "extern": {"imports": [], "body": []},
            "query": 'from(bucket: "jerry/funnyguy")\n|> range(start:2021-04-03T12:44:50Z, stop:now())\n|> filter(fn: (r) => r["_measurement"] == "indicators" and r["_field"] =~ /hit_fraction.?/)\n|> filter(fn: (r) => r["ci"] == "1")\n|> filter(fn: (r) => r["goals"] == "david,newman,puddy")\n|> filter(fn: (r) => r["outcome"] == "SOUP")\n|> group(columns: ["_measurement", "_field"], mode:"by")\n|> mean(column: "_value")',
            "dialect": {
                "header": True,
                "delimiter": ",",
                "annotations": ["datatype", "group", "default"],
                "commentPrefix": "#",
                "dateTimeFormat": "RFC3339",
            },
        }
        assert reqs[1].json_body() == {
            "extern": {"imports": [], "body": []},
            "query": 'from(bucket: "jerry/funnyguy")\n|> range(start:2021-04-03T12:44:50Z, stop:now())\n|> filter(fn: (r) => r["_measurement"] == "indicators" and r["_field"] =~ /saved_cpu_time.?|hits|total/)\n|> filter(fn: (r) => r["ci"] == "1")\n|> filter(fn: (r) => r["goals"] == "david,newman,puddy")\n|> filter(fn: (r) => r["outcome"] == "SOUP")\n|> group(columns: ["_measurement", "_field"], mode:"by")\n|> sum(column: "_value")',
            "dialect": {
                "header": True,
                "delimiter": ",",
                "annotations": ["datatype", "group", "default"],
                "commentPrefix": "#",
                "dateTimeFormat": "RFC3339",
            },
        }

    def test_query_missing_bucket(self, mock_client, repo: Repo) -> None:
        store = PantsMetricsStore.for_repo(repo)
        mock_client.add_missing_bucket_query_response("jerry/funnyguy")
        start = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        with pytest.raises(
            MissingBucketError, match='failed to initialize execute state: could not find bucket "jerry/funnyguy"'
        ):
            store.query_hit_fractions(start_datetime=start, end_datetime=None, filters={})

    def test_query_http_error(self, mock_client, repo: Repo) -> None:
        store = PantsMetricsStore.for_repo(repo)
        mock_client.add_json_response(
            method="POST", path="/api/v2/query", status=503, json_data={"code": "happy festivus"}
        )
        start = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        with pytest.raises(ApiException, match=r"HTTP response headers"):
            store.query_sums(start_datetime=start, end_datetime=None, filters={})

    def test_store_metrics_missing_bucket(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        mock_client.add_missing_bucket_write_response("jerry/funnyguy")
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts, indicators=self._get_fake_indicators())
        metrics_file = self._get_metrics_file()
        with pytest.raises(
            MissingBucketError, match='failed to initialize execute state: could not find bucket "jerry/funnyguy"'
        ):
            store.store_metrics(run_info=fake_ri, user=user, metrics_file=metrics_file)
        self._assert_write_request(mock_client.get_request())

    def test_store_metrics_http_40x_error(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        mock_client.add_json_response(
            method="POST", path="/api/v2/write", status=400, json_data={"reason": "happy festivus"}
        )
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts, indicators=self._get_fake_indicators())
        metrics_file = self._get_metrics_file()
        with pytest.raises(ApiException, match=r"HTTP response headers"):
            store.store_metrics(run_info=fake_ri, user=user, metrics_file=metrics_file)
        self._assert_write_request(mock_client.get_request())

    def test_store_metrics_http_500_error(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        mock_client.add_json_response(
            method="POST", path="/api/v2/write", status=500, json_data={"reason": "happy festivus"}
        )
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts, indicators=self._get_fake_indicators())
        metrics_file = self._get_metrics_file()
        with pytest.raises(MetricsStoreTransientError, match=r"HTTP error storing metrics.*happy festivus") as exc_info:
            store.store_metrics(run_info=fake_ri, user=user, metrics_file=metrics_file)
        assert exc_info.value.call_name == "store_pants_metrics"
        self._assert_write_request(mock_client.get_request())

    def test_store_metrics_network_error(self, mock_client, repo: Repo, user: ToolchainUser) -> None:
        error = NewConnectionError(pool="george", message="I was in a pool")  # type: ignore[call-arg]
        mock_client.add_network_error(method="POST", path="/api/v2/write", error=error)
        store = PantsMetricsStore.for_repo(repo)
        ts = datetime.datetime(2021, 4, 3, 12, 44, 50, tzinfo=datetime.timezone.utc)
        fake_ri = self._get_fake_run_info(ts, indicators=self._get_fake_indicators())
        metrics_file = self._get_metrics_file()
        with pytest.raises(
            MetricsStoreTransientError, match=r"Network error storing metrics.*george: I was in a pool"
        ) as exc_info:
            store.store_metrics(run_info=fake_ri, user=user, metrics_file=metrics_file)
        assert exc_info.value.call_name == "store_pants_metrics"
        self._assert_write_request(mock_client.get_request())
