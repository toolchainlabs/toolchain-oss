# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.hook_handlers.app_handlers_test import load_github_event
from toolchain.github_integration.hook_handlers.repo_handlers import handle_github_repo_event
from toolchain.github_integration.models import GithubRepo


@pytest.mark.django_db()
class TestRepoWebhookHandlers:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def _assert_bucket_empty(self) -> None:
        assert_bucket_empty(S3(), self._BUCKET)

    def _create_repo(self, github_repo_id: str) -> Repo:
        customer = Customer.create("festivus", name="Festivus to the rest of us")
        repo = Repo.create("tinsel", customer, "Tinsel Repo")
        GithubRepo.activate_or_create(
            install_id="77332", repo_id=github_repo_id, repo_name="tinsel", customer_id=customer.id
        )
        return repo

    def test_pull_request_open(self) -> None:
        fixture = load_github_event("pull_request_opened")
        repo = self._create_repo(github_repo_id="51405305")
        self._assert_bucket_empty()
        assert handle_github_repo_event(fixture) is True
        s3 = S3()
        key = f"jerry/hooks/festivs/pull_request/{repo.customer_id}/{repo.id}/0005769.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        contnet, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=key)
        assert content_type == "application/json"
        assert json.loads(contnet) == fixture.json_payload

    def test_pull_request_open_no_repo(self) -> None:
        fixture = load_github_event("pull_request_opened")
        assert handle_github_repo_event(fixture) is False
        self._assert_bucket_empty()

    def test_pull_request_assigned(self) -> None:
        fixture = load_github_event("pull_request_assigned")
        assert fixture.json_payload["repository"]["id"] == 51405305  # Sanity check
        self._create_repo(github_repo_id="51405305")
        assert handle_github_repo_event(fixture) is False
        self._assert_bucket_empty()

    def test_push_branch(self) -> None:
        fixture = load_github_event("repo_push_nested_branch")
        repo = self._create_repo(github_repo_id="51405305")
        self._assert_bucket_empty()
        assert handle_github_repo_event(fixture) is True
        key = f"jerry/hooks/festivs/push/{repo.customer_id}/{repo.id}/davis/cooks/fb667312699fbcd018649073e0acecdfd10b37ef.json"
        s3 = S3()
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        contnet, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=key)
        assert content_type == "application/json"
        assert json.loads(contnet) == fixture.json_payload

    def test_push_no_head(self) -> None:
        fixture = load_github_event("repo_push_branch")
        self._create_repo(github_repo_id="51405305")
        self._assert_bucket_empty()
        assert handle_github_repo_event(fixture) is False
        self._assert_bucket_empty()

    def test_push_tag(self) -> None:
        fixture = load_github_event("repo_push_tag")
        repo = self._create_repo(github_repo_id="51405305")
        self._assert_bucket_empty()
        assert handle_github_repo_event(fixture) is True
        key = (
            f"jerry/hooks/festivs/push/{repo.customer_id}/{repo.id}/poise/42ff059b3f078740e5b7cb10cbfec61b2670e6c9.json"
        )
        s3 = S3()
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        contnet, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=key)
        assert content_type == "application/json"
        assert json.loads(contnet) == fixture.json_payload

    def test_change_run_not_github_action(self) -> None:
        fixture = load_github_event("check_run_created_codecov_pull_request")
        assert fixture.json_payload["repository"]["id"] == 51405305  # Sanity check
        self._create_repo(github_repo_id="51405305")
        assert handle_github_repo_event(fixture) is False
        self._assert_bucket_empty()

    def test_change_run_github_action(self) -> None:
        fixture = load_github_event("check_run_created_github_actions_pull_request")
        assert fixture.json_payload["repository"]["id"] == 51405305  # Sanity check
        repo = self._create_repo(github_repo_id="51405305")
        assert handle_github_repo_event(fixture) is True
        key = f"jerry/hooks/festivs/check_run/{repo.customer_id}/{repo.id}/2008080037.json"
        s3 = S3()
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        contnet, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=key)
        assert content_type == "application/json"
        assert json.loads(contnet) == fixture.json_payload

    def test_change_run_github_action_missing_repo(self) -> None:
        fixture = load_github_event("check_run_created_github_actions_pull_request")
        assert fixture.json_payload["repository"]["id"] == 51405305  # Sanity check
        self._create_repo(github_repo_id="8888888")
        assert handle_github_repo_event(fixture) is False
        self._assert_bucket_empty()
