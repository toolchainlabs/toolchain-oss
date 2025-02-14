# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest
from moto import mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo, GithubRepoStatsConfiguration


@pytest.mark.django_db()
@pytest.mark.urls("toolchain.service.scm_integration.api.urls")
class TestResourcesCheckz:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def repo_stats(self) -> GithubRepoStatsConfiguration:
        return GithubRepoStatsConfiguration.create("jerry", period_minutes=99)

    @pytest.fixture()
    def config_repo(self) -> ConfigureGithubRepo:
        return ConfigureGithubRepo.create(repo_id="festivus")

    @pytest.fixture()
    def github_repo(self) -> GithubRepo:
        return GithubRepo.activate_or_create(repo_id="bob", install_id="jerry", repo_name="shrimp", customer_id="ocean")

    def test_resources_check_view(
        self,
        client,
        repo_stats: GithubRepoStatsConfiguration,
        config_repo: ConfigureGithubRepo,
        github_repo: GithubRepo,
    ) -> None:
        response = client.get("/checksz/resourcez")
        assert response.status_code == 200
        resp_json = response.json()
        test_time = datetime.datetime.fromisoformat(resp_json["s3"]["data"].pop("test-time"))
        assert resp_json == {
            "db": {
                "ConfigureGithubRepo": config_repo.pk,
                "GithubRepo": github_repo.id,
                "GithubRepoStatsConfiguration": repo_stats.pk,
            },
            "s3": {"bucket": "fake-scm-integration-bucket", "key": "lloyd/braun/testfile.json", "data": {}},
        }
        assert utcnow().timestamp() == pytest.approx(test_time.timestamp())

    def test_resources_check_view_empty_db(self, client) -> None:
        # In dev, the DB is usually empty, so we want to make sure we cover this use case.
        response = client.get("/checksz/resourcez")
        assert response.status_code == 200
        resp_json = response.json()
        test_time = datetime.datetime.fromisoformat(resp_json["s3"]["data"].pop("test-time"))
        assert resp_json == {
            "db": {
                "ConfigureGithubRepo": "NA",
                "GithubRepo": "NA",
                "GithubRepoStatsConfiguration": "NA",
            },
            "s3": {"bucket": "fake-scm-integration-bucket", "key": "lloyd/braun/testfile.json", "data": {}},
        }
        assert utcnow().timestamp() == pytest.approx(test_time.timestamp())
