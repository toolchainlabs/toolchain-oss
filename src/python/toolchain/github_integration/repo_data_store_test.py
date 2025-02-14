# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import json
from collections.abc import Sequence

import pytest
from django.core.cache import cache
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.client.repo_clients_test import load_fixture
from toolchain.github_integration.models import GithubRepo
from toolchain.github_integration.repo_data_store import GithubRepoDataStore, RepoStat


def add_fake_prs(bucket: str, repo: Repo, pr_numbers: Sequence[int]) -> None:
    s3 = S3()
    base_key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/"
    for num in pr_numbers:
        s3.upload_json_str(
            bucket=bucket,
            key=f"{base_key}{num}.json",
            json_str=json.dumps(
                {
                    "id": num * 200,
                    "number": num,
                    "title": "No soup for you come back one year",
                }
            ),
        )


@pytest.mark.django_db()
class TestGithubRepoDataStore:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def repo(self) -> Repo:
        customer = Customer.create("festivus", name="Festivus to the rest of us")
        return Repo.create("tinsel", customer, "Tinsel Repo")

    @pytest.fixture()
    def github_repo(self, repo: Repo) -> GithubRepo:
        return GithubRepo.activate_or_create(
            install_id="77332", repo_id="8833", repo_name="tinsel", customer_id=repo.customer_id
        )

    def test_store_pr_from_webhook(self, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("pull_request_opened")["payload"]
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        store.save_pull_request_from_webhook(fixture)
        s3 = S3()
        key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/0005769.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == fixture
        assert key in cache
        assert json.loads(cache.get(key)) == fixture

    def test_store_issue_from_webhook(self, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("repo_reopen_issue")["payload"]
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        store.save_issue_from_webhook(fixture)
        s3 = S3()
        key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/0012828.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == fixture
        assert key not in cache

    def test_store_pr_from_api(self, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("list_repo_issues")[1]
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        assert store.save_pull_request_from_api(fixture) is True
        s3 = S3()
        key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/0014388.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == fixture

    def test_store_pr_from_api_existing(self, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("list_repo_issues")[1]
        key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/0014388.json"
        s3 = S3()
        s3.upload_json_str(bucket=self._BUCKET, key=key, json_str=json.dumps({"jerry": "hello"}))
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        assert store.save_pull_request_from_api(fixture) is True
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == fixture

    def test_get_pr_webhook(self, client) -> None:
        fixture = load_fixture("pull_request_synchronize")["payload"]
        S3().upload_json_str(
            bucket=self._BUCKET, key="lloyd/braun/pull_request/kramer/ovaltine/5002.json", json_str=json.dumps(fixture)
        )
        store = GithubRepoDataStore(customer_id="kramer", repo_id="ovaltine")
        assert store.get_pull_request_data("5002") == fixture["pull_request"]
        assert "lloyd/braun/pull_request/kramer/ovaltine/5002.json" in cache
        assert json.loads(cache.get("lloyd/braun/pull_request/kramer/ovaltine/5002.json")) == fixture

    def test_get_pull_request_data_on_issue_from_api_with_old_format(self, client) -> None:
        fixture = load_fixture("list_repo_issues")[0]
        S3().upload_json_str(
            bucket=self._BUCKET, key="lloyd/braun/pull_request/kramer/ovaltine/14393.json", json_str=json.dumps(fixture)
        )
        store = GithubRepoDataStore(customer_id="kramer", repo_id="ovaltine")
        assert store.get_pull_request_data("14393") is None

    def test_get_pull_request_data_on_issue_from_api(self, client) -> None:
        fixture = load_fixture("list_repo_issues")[0]
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="lloyd/braun/pull_request/kramer/ovaltine/0014393.json",
            json_str=json.dumps(fixture),
        )
        store = GithubRepoDataStore(customer_id="kramer", repo_id="ovaltine")
        assert store.get_pull_request_data("14393") is None

    def test_get_non_existent_pr(self, client) -> None:
        store = GithubRepoDataStore(customer_id="kramer", repo_id="ovaltine")
        assert store.get_pull_request_data("5002") is None

    def test_get_pull_request_data_on_issue_webhook(self, client) -> None:
        fixture = load_fixture("issue_milestone_webhook_payload")
        S3().upload_json_str(
            bucket=self._BUCKET, key="lloyd/braun/pull_request/kramer/ovaltine/14733.json", json_str=json.dumps(fixture)
        )
        store = GithubRepoDataStore(customer_id="kramer", repo_id="ovaltine")
        assert store.get_pull_request_data("14733") is None

    def test_for_github_repo_id_invalid_repo(self):
        assert GithubRepoDataStore.for_github_repo_id("555122") is None

    def test_store_push(self, repo: Repo, github_repo: GithubRepo) -> None:
        push_data = load_fixture("repo_push")["payload"]
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        store.save_push(push_data)
        s3 = S3()
        key = f"lloyd/braun/push/{repo.customer_id}/{repo.id}/master/bb7dc6a6e4fdc8271d455dc423f0f5241fee5804.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == push_data
        assert key in cache
        assert json.loads(cache.get(key)) == push_data

    def test_store_push_nested_branch(self, repo: Repo, github_repo: GithubRepo) -> None:
        push_data = load_fixture("repo_push_nested_branch")["payload"]
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        store.save_push(push_data)
        s3 = S3()
        key = f"lloyd/braun/push/{repo.customer_id}/{repo.id}/davis/cooks/fb667312699fbcd018649073e0acecdfd10b37ef.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == push_data
        assert key in cache
        assert json.loads(cache.get(key)) == push_data

    def test_get_push(self, client) -> None:
        fixture = load_fixture("repo_push_nested_branch")["payload"]
        S3().upload_json_str(
            bucket=self._BUCKET, key="lloyd/braun/push/cosmo/costanza/berry/tinsel.json", json_str=json.dumps(fixture)
        )
        store = GithubRepoDataStore(customer_id="cosmo", repo_id="costanza")
        assert store.get_push_data(ref_name="berry", commit_sha="tinsel") == fixture
        assert "lloyd/braun/push/cosmo/costanza/berry/tinsel.json" in cache
        assert json.loads(cache.get("lloyd/braun/push/cosmo/costanza/berry/tinsel.json")) == fixture

    def test_get_push_from_cache(self, client) -> None:
        fixture = load_fixture("repo_push_nested_branch")["payload"]
        s3 = S3()
        s3.upload_json_str(
            bucket=self._BUCKET, key="lloyd/braun/push/cosmo/costanza/berry/tinsel.json", json_str=json.dumps(fixture)
        )
        store = GithubRepoDataStore(customer_id="cosmo", repo_id="costanza")
        assert store.get_push_data(ref_name="berry", commit_sha="tinsel") == fixture
        assert "lloyd/braun/push/cosmo/costanza/berry/tinsel.json" in cache
        assert json.loads(cache.get("lloyd/braun/push/cosmo/costanza/berry/tinsel.json")) == fixture
        # Delete the object from s3 so the test will break if the cache doesn't get hit.
        s3.delete_object(bucket=self._BUCKET, key="lloyd/braun/push/cosmo/costanza/berry/tinsel.json")
        store = GithubRepoDataStore(customer_id="cosmo", repo_id="costanza")
        assert store.get_push_data(ref_name="berry", commit_sha="tinsel") == fixture

    def test_save_repo_stats_data(self, repo: Repo, github_repo: GithubRepo) -> None:
        s3 = S3()
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        timestamp = utcnow()
        mock_repo_stats = {"fake_github_stats_key": "fake_github_stats_value"}
        store.save_repo_stats_data(RepoStat.RepoInfo, mock_repo_stats, timestamp)
        timestamp_str = timestamp.isoformat(timespec="minutes")
        key = f"fake-github-stats/{repo.customer_id}/{repo.id}/{timestamp_str}/repo_info.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == mock_repo_stats
        assert key not in cache

    def test_save_check_run(self, repo: Repo, github_repo: GithubRepo) -> None:
        check_run_payload = load_fixture("check_run_created_codecov_pull_request")["payload"]
        store = GithubRepoDataStore.for_github_repo_id("8833")
        assert store is not None
        store.save_check_run(check_run_payload)
        s3 = S3()
        key = f"lloyd/braun/check_run/{repo.customer_id}/{repo.id}/2008080247.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == check_run_payload
        assert key not in cache

    def test_get_check_run(self) -> None:
        fixture = load_fixture("check_run_completed_fail_github_actions_pull_request")["payload"]
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="lloyd/braun/check_run/importer/exporter/2008080037.json",
            json_str=json.dumps(fixture),
        )
        store = GithubRepoDataStore(customer_id="importer", repo_id="exporter")
        check_run = store.get_check_run("2008080037")
        assert check_run is not None
        assert check_run.run_id == "2008080037"
        assert check_run.suite_id == "2153510614"
        assert check_run.status == "completed"
        assert check_run.head_sha == "a7b1feefa6b53acaa6079bca322f272fd28ac7c9"
        assert check_run.repository_id == "51405305"
        assert check_run.conclusion == "failure"
        assert check_run.started_at == datetime.datetime(2021, 3, 1, 22, 3, 46, tzinfo=datetime.timezone.utc)
        assert "lloyd/braun/check_run/importer/exporter/2008080037.json" in cache
        assert json.loads(cache.get("lloyd/braun/check_run/importer/exporter/2008080037.json")) == fixture

    def test_get_check_run_missing(self) -> None:
        fixture = load_fixture("check_run_completed_fail_github_actions_pull_request")["payload"]
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="lloyd/braun/check_run/latex/salesman/2008080037.json",
            json_str=json.dumps(fixture),
        )
        store = GithubRepoDataStore(customer_id="latex", repo_id="salesman")
        assert store.get_check_run("20080800") is None
        assert "lloyd/braun/check_run/latex/salesman/2008080037.json" not in cache

    def test_for_github_repo_id_no_github_repo(self) -> None:
        assert GithubRepoDataStore.for_github_repo_id(github_repo_id="jerry") is None

    def test_for_github_repo_id_inactive_repo(self, repo: Repo, github_repo: GithubRepo) -> None:
        assert GithubRepoDataStore.for_github_repo_id(github_repo_id=github_repo.repo_id) is not None
        repo.deactivate()
        assert GithubRepoDataStore.for_github_repo_id(github_repo_id=github_repo.repo_id) is None

    def test_get_all_issue_numbers(self, repo: Repo, github_repo: GithubRepo) -> None:
        add_fake_prs(self._BUCKET, repo, pr_numbers=(8, 30, 22, 17, 2, 5))
        store = GithubRepoDataStore.for_github_repo_id(github_repo_id=github_repo.repo_id)
        assert store is not None
        issues = store.get_all_issue_numbers()
        assert issues == [2, 5, 8, 17, 22, 30]
