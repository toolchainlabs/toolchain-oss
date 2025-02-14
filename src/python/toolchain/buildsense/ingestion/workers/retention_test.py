# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from collections.abc import Sequence

import pytest
from freezegun import freeze_time
from moto import mock_dynamodb, mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.buildsense.ingestion.models import ProcessBuildDataRetention
from toolchain.buildsense.ingestion.run_info_raw_store_test import store_data
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_info_table_test import BaseRunInfoTableTests
from toolchain.buildsense.ingestion.workers.pants_runs_test import BaseWorkerTests
from toolchain.buildsense.records.run_info import RunKey
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.buildsense.test_utils.table_utils import get_table_items_count
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.util.test.elastic_search_util import DummyElasticRequests
from toolchain.workflow.models import WorkUnit


class TestBuildDataRetention(BaseWorkerTests):
    _BUCKET = "fake-test-buildsense-bucket"
    _FIXTURE_NAMES = (
        "run_test_with_coverage",
        "ci_pr_pants_run",
        "run_test_with_metrics_histograms",
        "bitbucket_branch_lint_run",
    )

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb(), mock_s3():
            create_s3_bucket(self._BUCKET)
            RunInfoTable.create_table()
            yield

    @pytest.fixture(autouse=True)
    def _start_mock_es(self):
        DummyElasticRequests.reset()

    def _assert_es_request(self, repo, lte_time: datetime.datetime) -> None:
        assert DummyElasticRequests.get_request().get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": repo.customer_id}},
                        {"term": {"repo_id": repo.id}},
                        {"range": {"timestamp": {"format": "epoch_second", "lte": lte_time.timestamp()}}},
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 20,
        }

    def _seed_builds(
        self, repo: Repo, user: ToolchainUser, es_response_count: int, fixture_names: Sequence[str]
    ) -> None:
        bt = datetime.datetime(2021, 7, 1, 18, 3, tzinfo=datetime.timezone.utc)

        run_ids = BaseRunInfoTableTests.seed_dynamodb_data(repo=repo, user=user, base_time=bt, fixtures=fixture_names)
        for name in fixture_names:
            store_data(user, repo, build_data=load_fixture(name))
        run_keys = [RunKey(user_api_id=user.api_id, repo_id=repo.id, run_id=run_id) for run_id in run_ids]
        run_infos = RunInfoTable.for_customer_id(repo.customer_id).get_by_run_ids(run_keys=run_keys)
        DummyElasticRequests.add_search_response(run_infos=run_infos[:es_response_count])
        # Sanity check
        assert get_table_items_count() == len(fixture_names)
        assert len(set(S3().keys_with_prefix(bucket=self._BUCKET, key_prefix=""))) == len(fixture_names)

    def test_no_op(self, repo: Repo) -> None:
        ProcessBuildDataRetention.create_or_update_for_repo(repo=repo)
        DummyElasticRequests.add_empty_search_response()
        with freeze_time(datetime.datetime(2021, 12, 12, 16, 3, tzinfo=datetime.timezone.utc)):
            assert self.do_work() == 1
        self._assert_es_request(repo, datetime.datetime(1996, 12, 17, tzinfo=datetime.timezone.utc))
        bdr = ProcessBuildDataRetention.objects.first()
        assert bdr.work_unit.state == WorkUnit.SUCCEEDED

    def test_delete_data(self, repo: Repo, user: ToolchainUser) -> None:
        self._seed_builds(repo, user, 2, fixture_names=self._FIXTURE_NAMES)
        ProcessBuildDataRetention.create_or_update_for_repo(repo=repo, retention_days=20, dry_run=False)
        assert self.do_work() == 1
        DummyElasticRequests.get_request()
        bdr = ProcessBuildDataRetention.objects.first()
        assert bdr.work_unit.state == WorkUnit.LEASED  # Since we deleted data.
        keys = set(S3().keys_with_prefix(bucket=self._BUCKET, key_prefix=""))
        assert len(keys) == 2
        path_prefix = f"no-soup-for-you/buildsense/storage/{repo.customer.id}/{repo.id}/{user.api_id}"
        assert keys == {
            f"{path_prefix}/pants_run_2021_03_03_01_33_16_256_db427ffef54a45baa8a601c29aa2a93a/final.json",
            f"{path_prefix}/pants_run_2021_08_11_00_14_51_48_c840708568b44cf48d76d42491978efb/final.json",
        }
        assert get_table_items_count() == 2

    def test_delete_data_inactive_repo_all_data(self, repo: Repo, user: ToolchainUser) -> None:
        self._seed_builds(repo, user, 2, fixture_names=self._FIXTURE_NAMES)
        ProcessBuildDataRetention.create_or_update_for_repo(repo=repo, retention_days=0, dry_run=False)
        repo.deactivate()
        assert self.do_work() == 1
        DummyElasticRequests.get_request()
        bdr = ProcessBuildDataRetention.objects.first()
        assert bdr.work_unit.state == WorkUnit.LEASED

    def test_delete_data_completed(self, repo: Repo) -> None:
        DummyElasticRequests.add_empty_search_response()
        ProcessBuildDataRetention.create_or_update_for_repo(repo=repo, retention_days=0, dry_run=False)
        repo.deactivate()
        assert self.do_work() == 1
        DummyElasticRequests.get_request()
        bdr = ProcessBuildDataRetention.objects.first()
        assert bdr.work_unit.state == WorkUnit.SUCCEEDED
