# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from urllib3.exceptions import ConnectTimeoutError

from toolchain.buildsense.ingestion.models import ConfigureRepoMetricsBucket, IndexPantsMetrics, ProcessPantsRun
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.common import FileInfo
from toolchain.buildsense.ingestion.workers.metrics import PantsMetricsIndexer
from toolchain.buildsense.ingestion.workers.pants_runs_test import BaseWorkerTests
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.test_utils.data_loader import get_fake_request_context, load_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.util.influxdb.mock_metrics_store import (
    assert_create_bucket_request,
    assert_delete_bucket_request,
    assert_get_buckets_request,
    assert_update_bucket_request,
    mock_rest_client,
)
from toolchain.workflow.models import WorkUnit


class TestPantsMetricsIndexer(BaseWorkerTests):
    @pytest.fixture()
    def mock_client(self):
        with mock_rest_client() as mock_client:
            yield mock_client

    def _prep_build(
        self, build_stats_fixture: str, repo: Repo, user: ToolchainUser, metrics: dict | None = None
    ) -> RunInfo:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        pdi = PantsDataIngestion.for_repo(repo=repo)
        build_data = load_fixture(build_stats_fixture)
        run_id = build_data["run_info"]["id"]
        created = pdi.store_build_ended(
            build_stats=build_data,
            user=user,
            impersonated_user=None,
            request_ctx=get_fake_request_context(
                request_id="Frogger", accept_time=datetime.datetime(2021, 4, 22, 18, 0, 0, tzinfo=datetime.timezone.utc)
            ),
        )
        ProcessPantsRun.objects.get(run_id=run_id).work_unit.delete()
        assert created is True
        run_info = table.get_by_run_id(repo_id=repo.id, user_api_id=user.api_id, run_id=run_id)
        info_store = RunInfoRawStore.for_repo(repo=repo)
        if not metrics:
            return run_info
        file_info = FileInfo.create_json_file(name="aggregate_metrics", json_data=[{"content": metrics}])
        info_store.save_build_file(
            run_id=run_id,
            content_or_file=file_info.content,
            content_type=file_info.content_type,
            name=file_info.name,
            user_api_id=user.api_id,
            dry_run=False,
            is_compressed=file_info.compressed,
            mode=WriteMode.OVERWRITE,
        )
        return run_info

    def _assert_write_request(self, request, user: ToolchainUser) -> None:
        assert request.query_params == [("org", "buildsense"), ("bucket", "ovaltine/goldjerry"), ("precision", "ns")]
        assert (
            request.body.decode()
            == f"workunits,branch=seinfeld,ci=0,context=desktop,goals=fmt,outcome=SUCCESS,pants_version=2.0.0.dev6,user_api_id={user.api_id},username=kenny local_execution=2i,shirt=0i 1596584147000000000"
        )

    def test_no_op(self, repo: Repo, user: ToolchainUser, mock_client) -> None:
        run_info = self._prep_build("build_end_workunits_v3", repo, user)
        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        worker = PantsMetricsIndexer()
        assert worker.do_work(ipm) is True
        mock_client.assert_no_requests()

    def test_ingest_metrics(self, repo: Repo, user: ToolchainUser, mock_client) -> None:
        run_info = self._prep_build(
            "build_end_workunits_v3", repo, user, metrics={"local_execution_requests": 2, "shirt": 0}
        )
        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        worker = PantsMetricsIndexer()
        assert worker.do_work(ipm) is True
        request = mock_client.get_request()
        assert request.query_params == [("org", "buildsense"), ("bucket", "ovaltine/goldjerry"), ("precision", "ns")]
        assert (
            request.body.decode()
            == f"workunits,branch=jarmel,ci=0,context=desktop,outcome=SUCCESS,pants_version=1.28.0.dev1,user_api_id={user.api_id},username=kenny local_execution_requests=2i,shirt=0i 1588870458000000000"
        )

    def test_inactive_repo(self, repo: Repo, user: ToolchainUser, mock_client) -> None:
        run_info = self._prep_build(
            "build_end_workunits_v3", repo, user, metrics={"local_execution_requests": 2, "shirt": 0}
        )
        repo.deactivate()
        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        worker = PantsMetricsIndexer()
        assert worker.do_work(ipm) is True
        mock_client.assert_not_used()

    def test_index_pants_metrics_deleted(self, user: ToolchainUser, repo: Repo, mock_client) -> None:
        run_info = load_run_info("black_fmt_with_artifacts", repo, user)
        IndexPantsMetrics.create_or_rerun(run_info, repo=repo).mark_as_deleted()
        assert self.do_work() == 1
        loaded_ipm = IndexPantsMetrics.objects.first()
        assert loaded_ipm.work_unit.state == WorkUnit.SUCCEEDED
        mock_client.assert_not_used()

    def test_index_pants_metrics_missing_bucket(self, user: ToolchainUser, repo: Repo, mock_client) -> None:
        mock_client.add_missing_bucket_write_response("jerry/funnyguy")
        run_info = self._prep_build("black_fmt_with_artifacts", repo, user, metrics={"local_execution": 2, "shirt": 0})
        IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert self.do_work() == 1
        loaded_wu = IndexPantsMetrics.objects.first().work_unit
        assert loaded_wu.state == WorkUnit.PENDING
        assert loaded_wu.num_unsatisfied_requirements == loaded_wu.requirements.count() == 1
        crmb = loaded_wu.requirements.first().payload
        assert isinstance(crmb, ConfigureRepoMetricsBucket)
        assert crmb.repo_id == repo.id
        self._assert_write_request(mock_client.get_request(), user)

    def test_index_pants_metrics_transient_http_500_error(self, user: ToolchainUser, repo: Repo, mock_client) -> None:
        mock_client.add_json_response(
            method="POST", path="/api/v2/write", status=500, json_data={"reason": "happy festivus"}
        )
        run_info = self._prep_build("black_fmt_with_artifacts", repo, user, metrics={"local_execution": 2, "shirt": 0})
        IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert self.do_work() == 1
        loaded_wu = IndexPantsMetrics.objects.first().work_unit
        assert loaded_wu.state == WorkUnit.LEASED
        self._assert_write_request(mock_client.get_request(), user)

    def test_index_pants_metrics_transient_http_401_error(self, user: ToolchainUser, repo: Repo, mock_client) -> None:
        mock_client.add_json_response(
            method="POST", path="/api/v2/write", status=401, json_data={"reason": "happy festivus"}
        )
        run_info = self._prep_build("black_fmt_with_artifacts", repo, user, metrics={"local_execution": 2, "shirt": 0})
        IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert self.do_work() == 1
        loaded_wu = IndexPantsMetrics.objects.first().work_unit
        assert loaded_wu.state == WorkUnit.INFEASIBLE
        self._assert_write_request(mock_client.get_request(), user)

    def test_index_pants_metrics_transient_network_error(self, user: ToolchainUser, repo: Repo, mock_client) -> None:
        mock_client.add_network_error(method="POST", path="/api/v2/write", error=ConnectTimeoutError("buck naked"))
        run_info = self._prep_build("black_fmt_with_artifacts", repo, user, metrics={"local_execution": 2, "shirt": 0})
        IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert self.do_work() == 1
        loaded_wu = IndexPantsMetrics.objects.first().work_unit
        assert loaded_wu.state == WorkUnit.LEASED
        self._assert_write_request(mock_client.get_request(), user)


class TestPantsMetricsConfigurator(BaseWorkerTests):
    @pytest.fixture()
    def mock_client(self):
        with mock_rest_client() as mock_client:
            yield mock_client

    def test_configure_bucket_for_repo_new_bucket(self, repo: Repo, mock_client) -> None:
        ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        mock_client.add_get_buckets_response()
        mock_client.add_get_orgs_response()
        mock_client.add_create_bucket_response("ovaltine/goldjerry")
        assert self.do_work() == 1
        loaded_crmb = ConfigureRepoMetricsBucket.objects.first()
        assert loaded_crmb.work_unit.state == WorkUnit.SUCCEEDED
        requests = mock_client.get_requests()
        assert len(requests) == 3
        assert_get_buckets_request(requests[0], "ovaltine/goldjerry")
        assert_create_bucket_request(requests[2], "ovaltine/goldjerry", retention_seconds=31536000)

    def test_configure_bucket_for_repo_existing(self, repo: Repo, mock_client) -> None:
        ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        mock_client.add_get_buckets_response_with_id("ovaltine/goldjerry", bucket_id="blueberry")
        mock_client.add_get_orgs_response()
        mock_client.add_update_bucket_response("ovaltine/goldjerry", bucket_id="blueberry")
        assert self.do_work() == 1
        loaded_crmb = ConfigureRepoMetricsBucket.objects.first()
        assert loaded_crmb.work_unit.state == WorkUnit.SUCCEEDED
        requests = mock_client.get_requests()
        assert len(requests) == 2
        assert_get_buckets_request(requests[0], "ovaltine/goldjerry")
        assert_update_bucket_request(
            requests[1], "ovaltine/goldjerry", bucket_id="blueberry", retention_seconds=31536000
        )

    def test_delete_bucket_for_inactive_repo(self, repo: Repo, mock_client) -> None:
        repo.deactivate()
        ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        mock_client.add_get_buckets_response_with_id("ovaltine/goldjerry", bucket_id="blueberry")
        mock_client.add_delete_bucket_response("blueberry")
        assert self.do_work() == 1
        loaded_crmb = ConfigureRepoMetricsBucket.objects.first()
        assert loaded_crmb.work_unit.state == WorkUnit.SUCCEEDED
        requests = mock_client.get_requests()
        assert len(requests) == 2
        assert_get_buckets_request(requests[0], "ovaltine/goldjerry")
        assert_delete_bucket_request(requests[1], bucket_id="blueberry")

    def test_invalid_repo(self) -> None:
        ConfigureRepoMetricsBucket.run_for_repo(repo_id="bob")
        assert self.do_work() == 1
        loaded_crmb = ConfigureRepoMetricsBucket.objects.first()
        assert loaded_crmb.work_unit.state == WorkUnit.INFEASIBLE
