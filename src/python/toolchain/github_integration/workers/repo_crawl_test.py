# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time
from moto import mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.models import GithubRepo, GithubRepoStatsConfiguration
from toolchain.github_integration.workers.dispatcher import GithubIntegrationWorkDispatcher
from toolchain.util.test.util import assert_messages
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests


class TestGithubRepoStats(BaseWorkflowWorkerTests):
    @pytest.fixture()
    def github_repo(self) -> GithubRepo:
        customer = Customer.create(slug="ovaltine", name="Ovaltine!")
        repo = Repo.create(name="George", slug="tinsel", customer=customer)
        return GithubRepo.activate_or_create(
            install_id="65544", repo_id="8833", repo_name=repo.slug, customer_id=customer.pk
        )

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket("fake-scm-integration-bucket")
            yield

    def get_dispatcher(self) -> type[GithubIntegrationWorkDispatcher]:
        return GithubIntegrationWorkDispatcher

    def add_mock_responses(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/app/installations/65544/access_tokens",
            json={
                "token": "gold-jerry-gold",
                "expires_at": "2020-06-03T22:14:10Z",
                "permissions": {"issues": "write", "contents": "read"},
                "repository_selection": "selected",
                "repositories": [],
            },
        )
        httpx_mock.add_response(
            method="GET", url="https://api.github.com/repos/ovaltine/tinsel", json={"mock_list": True}
        )
        httpx_mock.add_response(
            method="GET", url="https://api.github.com/repos/ovaltine/tinsel/traffic/views", json={"mock_views": True}
        )
        httpx_mock.add_response(
            method="GET", url="https://api.github.com/repos/ovaltine/tinsel/traffic/clones", json={"mock_clones": True}
        )
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/repos/ovaltine/tinsel/traffic/popular/paths",
            json={"mock_paths": True},
        )
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/repos/ovaltine/tinsel/traffic/popular/referrers",
            json={"mock_referrers": True},
        )

    def assert_work_unit_state(self, state: str) -> None:
        assert GithubRepoStatsConfiguration.objects.count() == 1
        wu = GithubRepoStatsConfiguration.objects.first().work_unit
        assert wu.state == state

    @freeze_time(datetime.datetime(2020, 6, 2, 16, 3, tzinfo=datetime.timezone.utc))
    def test_repeating_repo_stats_fetch(self, httpx_mock, github_repo: GithubRepo) -> None:
        self.add_mock_responses(httpx_mock)
        GithubRepoStatsConfiguration.create(repo_id=github_repo.repo_id, period_minutes=60 * 24)

        assert self.do_work() == 1
        self.assert_work_unit_state(WorkUnit.LEASED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 6
        requested_urls = {request.url for request in requests[1:]}
        assert "https://api.github.com/repos/ovaltine/tinsel" in requested_urls
        assert "https://api.github.com/repos/ovaltine/tinsel/traffic/clones" in requested_urls
        assert "https://api.github.com/repos/ovaltine/tinsel/traffic/views" in requested_urls
        assert "https://api.github.com/repos/ovaltine/tinsel/traffic/popular/paths" in requested_urls
        assert "https://api.github.com/repos/ovaltine/tinsel/traffic/popular/referrers" in requested_urls

    def test_one_off_repo_stats_fetch(self, httpx_mock, github_repo: GithubRepo) -> None:
        self.add_mock_responses(httpx_mock)
        GithubRepoStatsConfiguration.create(repo_id=github_repo.repo_id, period_minutes=None)
        assert self.do_work() == 1
        self.assert_work_unit_state(WorkUnit.SUCCEEDED)
        assert len(httpx_mock.get_requests()) == 6

    def test_no_repo_id_found_case(self, caplog) -> None:
        # no repo_id 77777 should exist
        GithubRepoStatsConfiguration.create(repo_id="77777", period_minutes=60 * 24)
        assert self.do_work() == 1
        self.assert_work_unit_state(WorkUnit.SUCCEEDED)
        assert_messages(caplog, "no repo found for repo_id 77777")
