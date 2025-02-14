# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.bitbucket_integration.repo_data_store import BitbucketRepoDataStore
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture_payload
from toolchain.django.site.models import Customer, Repo


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

    def test_store_pr(self, repo: Repo) -> None:
        payload = load_fixture_payload("pullrequest_created")
        store = BitbucketRepoDataStore.for_repo(repo)
        store.save_pull_request(payload)
        s3 = S3()
        key = f"moles/freckles/pull_request/{repo.customer_id}/{repo.id}/9.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == payload

    def test_store_branch_push(self, repo: Repo) -> None:
        payload = load_fixture_payload("repo_push_create_branch")
        store = BitbucketRepoDataStore.for_repo(repo)
        store.save_push(payload)
        s3 = S3()
        key = f"moles/freckles/push/{repo.customer_id}/{repo.id}/branch/upgrades/a1742195055d9234440410f95462fdebb05b5ac2.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == payload

    def test_get_pr(self, repo: Repo) -> None:
        payload = load_fixture_payload("pullrequest_updated")
        key = f"moles/freckles/pull_request/{repo.customer_id}/{repo.id}/7.json"
        S3().upload_json_str(bucket=self._BUCKET, key=key, json_str=json.dumps(payload))
        store = BitbucketRepoDataStore.for_repo(repo)
        pr_data = store.get_pull_request_data("7")
        assert pr_data == payload["data"]["pullrequest"]
        assert pr_data["type"] == "pullrequest"
        assert pr_data["id"] == 7
        assert pr_data["title"] == "Add linters"

    def test_store_tag_push(self, repo: Repo) -> None:
        payload = load_fixture_payload("repo_push_create_tag")
        store = BitbucketRepoDataStore.for_repo(repo)
        store.save_push(payload)
        s3 = S3()
        key = f"moles/freckles/push/{repo.customer_id}/{repo.id}/tag/feats-of-strength/d98f3c1d2ad48d6f7ed51281eb28ad3b233878c4.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert json.loads(s3.get_content(bucket=self._BUCKET, key=key)) == payload

    def test_get_push_data(self, repo: Repo) -> None:
        payload = load_fixture_payload("repo_push_create_tag")
        key = f"moles/freckles/push/{repo.customer_id}/{repo.id}/tag/soup/hello-newman.json"
        S3().upload_json_str(bucket=self._BUCKET, key=key, json_str=json.dumps(payload))
        store = BitbucketRepoDataStore.for_repo(repo)
        push_data = store.get_push_data(push_type="tag", ref_name="soup", commit_sha="hello-newman")
        assert push_data == payload["data"]
        assert push_data["push"]["changes"][0]["new"]["target"]["author"]["user"]["nickname"] == "Asher Foa"
        assert (
            push_data["push"]["changes"][0]["new"]["target"]["summary"]["raw"]
            == "Merged in upgrades (pull request #9)\n\nAdd & run linters"
        )
        assert push_data["actor"]["account_id"] == "6059303e630024006fab8c2b"

    def test_get_push_data_missing(self, repo: Repo) -> None:
        store = BitbucketRepoDataStore.for_repo(repo)
        assert store.get_push_data(push_type="tag", ref_name="soup", commit_sha="hello-newman") is None

    def test_store_push_delete_branch(self, repo: Repo) -> None:
        payload = load_fixture_payload("repo_push_delete_branch")
        store = BitbucketRepoDataStore.for_repo(repo)
        assert store.save_push(payload) is False
        assert_bucket_empty(S3(), self._BUCKET)
