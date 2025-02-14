# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from collections import OrderedDict
from urllib.parse import urlencode

import boto3
import pytest
from django.http import HttpResponse
from moto import mock_dynamodb, mock_s3
from opensearchpy import ConnectionTimeout
from rest_framework.test import APIClient

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.build_data_queries_test import add_build_artifacts, prepare_build_with_artifacts
from toolchain.buildsense.ingestion.metrics_store_test import add_hit_fractions_query_response, add_sums_query_response
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.records.run_info import RunInfo, ScmProvider, ServerInfo
from toolchain.buildsense.test_utils.data_loader import insert_build_data
from toolchain.buildsense.test_utils.fixtures_loader import load_bytes_fixture, load_fixture
from toolchain.django.auth.claims import UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.impersonation import ImpersonationData
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user, create_staff
from toolchain.util.influxdb.mock_metrics_store import mock_rest_client
from toolchain.util.test.elastic_search_util import DummyElasticRequests
from toolchain.util.test.util import convert_headers_to_wsgi


@pytest.mark.django_db()
class BaseTestViewsApi:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="acmeid", name="acme")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = create_github_user(
            username="kramer", email="kramer@jerrysplace.com", full_name="Cosmo Kramer", github_user_id="10109"
        )
        customer.add_user(user)
        return user

    @pytest.fixture()
    def staff_user(self, customer: Customer) -> ToolchainUser:
        user = create_staff(username="jerry", email="jerry@jerrysplace.com", github_user_id="776632")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def user_no_details(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="kenny", email="kenny.kramer@jerrysplace.com")
        customer.add_user(user)
        return user

    @pytest.fixture(autouse=True)
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("acmebotid", customer=customer, name="acmebot")

    def _get_headers_for_client(
        self, user: ToolchainUser, settings, impersonator: ToolchainUser | None
    ) -> dict[str, str]:
        claims = UserClaims(
            token_id=None,
            user_api_id=user.api_id,
            username=user.username,
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.ACCESS_TOKEN,
        )
        impersonation = (
            ImpersonationData(user=user, impersonator=impersonator, expiry=utcnow() + datetime.timedelta(hours=1))
            if impersonator
            else None
        )
        headers = create_internal_auth_headers(user, claims=claims.as_json_dict(), impersonation=impersonation)
        return convert_headers_to_wsgi(headers)

    def _get_client_for_user(
        self, user: ToolchainUser, settings, impersonator: ToolchainUser | None = None
    ) -> APIClient:
        headers = self._get_headers_for_client(user, settings=settings, impersonator=impersonator)
        client = APIClient(**headers)
        return client

    @pytest.fixture()
    def client(self, user: ToolchainUser, settings) -> APIClient:
        return self._get_client_for_user(user, settings)

    @pytest.fixture()
    def staff_user_client(self, staff_user: ToolchainUser, settings) -> APIClient:
        return self._get_client_for_user(staff_user, settings)

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb(), mock_s3():
            create_s3_bucket("fake-test-buildsense-bucket")
            RunInfoTable.create_table()
            yield

    @pytest.fixture(autouse=True)
    def _es_mock(self):
        DummyElasticRequests.reset()

    def store_s3(self, repo: Repo, user: ToolchainUser, raw_data: dict) -> tuple[str, str]:
        run_id = raw_data["run_info"]["id"]
        s3 = boto3.client("s3")
        base_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/{run_id}"
        key = f"{base_key}/final.json"
        s3.put_object(Bucket="fake-test-buildsense-bucket", Key=key, Body=json.dumps(raw_data).encode())
        if "platform" in raw_data:
            s3.put_object(
                Bucket="fake-test-buildsense-bucket",
                Key=f"{base_key}/platform_info.json",
                Body=json.dumps(raw_data["platform"]).encode(),
                ContentType="application/json",
            )

        return run_id, key

    def _store_build(
        self,
        repo: Repo,
        user: ToolchainUser,
        build_data: dict,
        build_time: datetime.datetime | None = None,
        add_scm_link: ScmProvider | None = None,
    ) -> RunInfo:
        pdi = PantsDataIngestion.for_repo(repo)
        run_id, key = self.store_s3(repo, user, build_data)
        dummy_server_info = ServerInfo(
            request_id="test",
            accept_time=build_time or datetime.datetime(2020, 1, 30, tzinfo=datetime.timezone.utc),
            stats_version="3",
            environment="jambalaya",
            s3_bucket="fake-test-buildsense-bucket",
            s3_key=key,
        )
        created, run_info = insert_build_data(pdi, build_data, user, dummy_server_info, add_scm_link=add_scm_link)
        assert created is True
        return run_info

    def _seed_dynamodb_data(
        self, repo: Repo, *users: ToolchainUser, build_time: datetime.datetime | None = None
    ) -> list[RunInfo]:
        build_time = (build_time or utcnow()) - datetime.timedelta(minutes=3)
        run_infos = []
        fixtures_and_users = [
            (load_fixture(f"sample{fixture_id}"), users[(fixture_id - 1) % len(users)]) for fixture_id in range(1, 7)
        ]
        fixtures_and_users.extend(
            [(load_fixture("ci_build_branch_final_1"), users[0]), (load_fixture("ci_build_pr_final_1"), users[0])]
        )
        for build_data, user in fixtures_and_users:
            build_time -= datetime.timedelta(hours=1)
            build_data["run_info"].pop("repo_id", None)
            build_data["run_info"]["timestamp"] = int(build_time.replace(tzinfo=datetime.timezone.utc).timestamp())
            run_info = self._store_build(repo, user, build_data, build_time)
            run_infos.append(run_info)
        return run_infos

    def _prepare_build_from_fixture(self, repo: Repo, user: ToolchainUser, fixture: str) -> tuple[RunInfo, str, dict]:
        raw_data = load_fixture(fixture)
        run_info = self._store_build(
            repo, user, raw_data, datetime.datetime(2019, 4, 22, 19, 24, 44, tzinfo=datetime.timezone.utc)
        )
        return run_info, run_info.server_info.s3_key, raw_data

    def _prepare_build(self, repo: Repo, user: ToolchainUser, fixture="sample3") -> tuple[str, str, dict, RunInfo]:
        build_time = datetime.datetime(2019, 4, 22, 19, 24, 44, tzinfo=datetime.timezone.utc)
        raw_data = load_fixture(fixture)
        run_info = self._seed_dynamodb_data(repo, user, build_time=build_time)[2]
        return run_info.run_id, run_info.server_info.s3_key, raw_data, run_info

    def _get_base_url(self, repo: Repo | str, run_id: str | None = None) -> str:
        repo_slug = repo if isinstance(repo, str) else repo.slug
        customer_slug = f"cust{repo}" if isinstance(repo, str) else repo.customer.slug
        url = f"/api/v1/repos/{customer_slug}/{repo_slug}/builds/"
        return f"{url}{run_id}/" if run_id else url


class TestSearchViewsApi(BaseTestViewsApi):
    def _get_builds(self, client, repo: Repo | str, data: dict | None = None) -> HttpResponse:
        url = self._get_base_url(repo)
        if data:
            return client.get(url, data=data)
        return client.get(url)

    @pytest.mark.parametrize(
        ("params", "errors"),
        [
            (
                {"sort": "foo"},
                {"sort": [("invalid_choice", "Select a valid choice. foo is not one of the available choices.")]},
            ),
            ({"page_size": "soup"}, {"page_size": [("invalid", "Enter a whole number.")]}),
            ({"page_size": "-1"}, {"page_size": [("min_value", "Ensure this value is greater than or equal to 1.")]}),
            ({"page_size": "88"}, {"page_size": [("max_value", "Ensure this value is less than or equal to 50.")]}),
            ({"earliest": "soup"}, {"earliest": [("invalid", "Enter a valid date/time.")]}),
            ({"latest": "soup"}, {"latest": [("invalid", "Enter a valid date/time.")]}),
            ({"latest": "2018-2-31 14:20:00"}, {"latest": [("invalid", "Enter a valid date/time.")]}),
            ({"earliest": "2019-2-29 3:20:00"}, {"earliest": [("invalid", "Enter a valid date/time.")]}),
            ({"latest": "2018-1-8 14:66:00"}, {"latest": [("invalid", "Enter a valid date/time.")]}),
            ({"latest": "2018-1-8 24:00:00"}, {"latest": [("invalid", "Enter a valid date/time.")]}),
            ({"latest": "2018-1-8 23:60:00"}, {"latest": [("invalid", "Enter a valid date/time.")]}),
            (
                {"earliest": "soup", "latest": "soup"},
                {
                    "earliest": [("invalid", "Enter a valid date/time.")],
                    "latest": [("invalid", "Enter a valid date/time.")],
                },
            ),
            (
                {"earliest": "2018-1-27 20:30:50", "latest": "2018-1-27 19:21:43"},
                {"__all__": [("range", "Invalid date range.")]},
            ),
            (
                {"earliest": "2018-1-27 16:30:50", "latest": "2018-1-27 19:21:43", "jerry": "hello!"},
                {"__all__": [("unexpected", "Got unexpected fields: jerry")]},
            ),
            (
                {
                    "earliest": "2018-1-27 16:30:50",
                    "latest": "2018-1-27 19:21:43",
                    "jerry": "hello!",
                    "kenny": "gold jerry gold",
                },
                {"__all__": [("unexpected", "Got unexpected fields: jerry, kenny")]},
            ),
        ],
    )
    def test_list_builds_invalid_params(self, client: APIClient, repo: Repo, params: dict, errors: dict) -> None:
        response = self._get_builds(client, repo, data=params)
        assert response.status_code == 400
        expected_errors = {}
        for field, errors_list in errors.items():
            expected_errors[field] = [{"code": code, "message": msg} for code, msg in errors_list]
        assert response.json() == {"errors": expected_errors}

    def test_list_builds_by_multiple_params_empty_results(self, client, repo, user, customer):
        DummyElasticRequests.add_empty_search_response()
        response = self._get_builds(client, repo, data={"cmd_line": "Happy, Pappy?", "outcome": "FAILURE"})
        assert response.status_code == 200
        build_data = response.json()["results"]
        assert len(build_data) == 0

    def test_list_builds_by_multiple_params(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        build_time = datetime.datetime(2018, 1, 22, 3, 20, 57, tzinfo=datetime.timezone.utc)
        run_infos = self._seed_dynamodb_data(repo, user, build_time=build_time)
        DummyElasticRequests.add_search_response(run_infos)
        response = self._get_builds(client, repo, data={"cmd_line": "test", "outcome": "failure"})
        assert response.status_code == 200
        # Note: our mocked ES doesn't do any filtering, so the params we pass to this API don't actually affect
        # the search results returned under test.
        assert len(response.json()["results"]) == 8
        results = response.json()["results"]
        assert results[3] == {
            "repo_id": repo.pk,
            "repo_slug": "acmebotid",
            "is_ci": False,
            "buildroot": "/Users/asher/projects/toolchain",
            "machine": "Ashers-MacBook-Pro.local",
            "version": "1.18.0.dev1",
            "path": "/Users/asher/projects/toolchain",
            "outcome": "FAILURE",
            "cmd_line": "pants fmt.isort prod/python:: src/python:: test/python::",
            "run_id": "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "user": {
                "api_id": user.api_id,
                "avatar_url": "https://pictures.jerry.com/gh-kramer",
                "full_name": "Cosmo Kramer",
                "username": "kramer",
            },
            "run_time": None,
            "title": None,
            "ci_info": None,
            "branch": None,
            "revision": None,
            "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969/",
            "datetime": "2018-01-21T23:17:57+00:00",
            "customer_id": customer.pk,
            "specs_from_command_line": [],
            "goals": [],
        }
        assert results[-1] == {
            "repo_id": repo.pk,
            "buildroot": "/home/toolchain/project",
            "machine": "c2fd5769a378",
            "version": "2.0.0.dev6",
            "path": "/home/toolchain/project",
            "outcome": "SUCCESS",
            "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
            "run_id": "pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427",
            "customer_id": customer.pk,
            "specs_from_command_line": ["prod/python::", "src/python::"],
            "run_time": None,
            "branch": "pull/6490",
            "revision": "c5454b4327903b7d2242f705e9218ca90bcc7e49",
            "title": "No soup for you come back one year!",
            "ci_info": {
                "username": "asherf",
                "run_type": "pull_request",
                "pull_request": 6490,
                "job_name": "build",
                "build_num": 22579.0,
                "links": [
                    {
                        "icon": "circleci",
                        "text": "build",
                        "link": "https://circleci.com/gh/toolchainlabs/toolchain/22579",
                    }
                ],
            },
            "user": {
                "username": "kramer",
                "full_name": "Cosmo Kramer",
                "api_id": user.api_id,
                "avatar_url": "https://pictures.jerry.com/gh-kramer",
            },
            "repo_slug": "acmebotid",
            "datetime": "2018-01-21T19:17:57+00:00",
            "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/",
            "is_ci": True,
            "goals": ["validate"],
        }

    def test_list_builds_by_empty_params(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        run_infos = self._seed_dynamodb_data(repo, user)
        DummyElasticRequests.add_search_response(run_infos)
        response = self._get_builds(client, repo)
        assert response.status_code == 200
        assert len(response.json()["results"]) == 8

    def _setup_builds_and_users(self, user: ToolchainUser, repo: Repo) -> list[RunInfo]:
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        u3 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        u4 = ToolchainUser.create(username="george", email="george@seinfeld.com")
        ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        ToolchainUser.create(username="elaine", email="elaine@seinfeld.com")
        return self._seed_dynamodb_data(repo, user, u2, u3, u4)

    def _setup_multi_user_data(self, user: ToolchainUser, repo: Repo) -> None:
        run_infos = self._setup_builds_and_users(user, repo)
        DummyElasticRequests.add_search_response(run_infos, override_total=91)

    def test_list_builds_by_cmd_line(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        # Note: our mocked ES doesn't do any filtering, so the params we pass to this API don't actually affect
        # the search results returned under test.
        # It will always return everything we pass to DummyElasticRequests.add_search_response
        response = self._get_builds(
            client, repo, data={"page_size": 22, "cmd_line": "Happy, Pappy?", "earliest": earliest_str}
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        assert build_data[0]["user"]["username"] == "kramer"
        assert build_data[1]["user"]["username"] == "jerry"
        assert build_data[2]["user"]["username"] == "cosmo"
        assert build_data[3]["user"]["username"] == "george"
        assert build_data[4]["user"]["username"] == "kramer"
        assert build_data[5]["user"]["username"] == "jerry"
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"match": {"cmd_line": "Happy, Pappy?"}},
                    ]
                }
            },
        }

    def test_list_builds_by_cmd_line_empty_results(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        DummyElasticRequests.add_empty_search_response()
        response = self._get_builds(client, repo, data={"cmd_line": "Happy, Pappy?"})
        assert response.status_code == 200
        build_data = response.json()["results"]
        assert len(build_data) == 0
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 20,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"match": {"cmd_line": "Happy, Pappy?"}},
                    ]
                }
            },
        }

    def test_list_builds_by_goals(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        # Note: our mocked ES doesn't do any filtering, so the params we pass to this API don't actually affect
        # the search results returned under test.
        # It will always return everything we pass to DummyElasticRequests.add_search_response
        response = self._get_builds(
            client, repo, data={"page_size": 22, "goals": "binary,test", "earliest": earliest_str}
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        assert build_data[0]["user"]["username"] == "kramer"
        assert build_data[1]["user"]["username"] == "jerry"
        assert build_data[2]["user"]["username"] == "cosmo"
        assert build_data[3]["user"]["username"] == "george"
        assert build_data[4]["user"]["username"] == "kramer"
        assert build_data[5]["user"]["username"] == "jerry"
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "minimum_should_match": 1,
                    "should": [
                        {"match_phrase": {"computed_goals": "binary"}},
                        {"match_phrase": {"computed_goals": "test"}},
                    ],
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                    ],
                }
            },
        }

    def test_list_builds_by_goals_with_whitespace(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        # Note: our mocked ES doesn't do any filtering, so the params we pass to this API don't actually affect
        # the search results returned under test.
        # It will always return everything we pass to DummyElasticRequests.add_search_response
        response = self._get_builds(
            client, repo, data={"page_size": 22, "goals": "binary,  test, typecheck,fmt  ", "earliest": earliest_str}
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        assert build_data[0]["user"]["username"] == "kramer"
        assert build_data[1]["user"]["username"] == "jerry"
        assert build_data[2]["user"]["username"] == "cosmo"
        assert build_data[3]["user"]["username"] == "george"
        assert build_data[4]["user"]["username"] == "kramer"
        assert build_data[5]["user"]["username"] == "jerry"
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "minimum_should_match": 1,
                    "should": [
                        {"match_phrase": {"computed_goals": "binary"}},
                        {"match_phrase": {"computed_goals": "test"}},
                        {"match_phrase": {"computed_goals": "typecheck"}},
                        {"match_phrase": {"computed_goals": "fmt"}},
                    ],
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                    ],
                }
            },
        }

    def test_list_builds_by_runtime_and_goal(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={
                "page_size": 22,
                "goals": "test,lint",
                "run_time_min": "30",
                "run_time_max": "1200",
                "earliest": earliest_str,
            },
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "minimum_should_match": 1,
                    "should": [
                        {"match_phrase": {"computed_goals": "test"}},
                        {"match_phrase": {"computed_goals": "lint"}},
                    ],
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"range": {"run_time": {"gte": 30_000, "lte": 1_200_000}}},
                    ],
                }
            },
        }

    def test_list_builds_by_runtime_min(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "goals": "test,lint", "run_time_min": "90", "earliest": earliest_str},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "minimum_should_match": 1,
                    "should": [
                        {"match_phrase": {"computed_goals": "test"}},
                        {"match_phrase": {"computed_goals": "lint"}},
                    ],
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"range": {"run_time": {"gte": 90_000}}},
                    ],
                }
            },
        }

    def test_list_builds_by_runtime_max(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "goals": "lint", "run_time_max": "240", "earliest": earliest_str},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"match_phrase": {"computed_goals": "lint"}},
                        {"range": {"run_time": {"lte": 240_000}}},
                    ],
                }
            },
        }

    def test_list_builds_invalid_runtime(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={
                "page_size": 22,
                "goals": "test,lint",
                "run_time_min": "800",
                "run_time_max": "60",
                "earliest": earliest_str,
            },
        )
        assert response.status_code == 400
        json_response = response.json()
        assert json_response == {"errors": {"__all__": [{"message": "Invalid run time range.", "code": "range"}]}}
        DummyElasticRequests.assert_no_requests()

    def test_list_build_by_user_and_ci(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "earliest": earliest_str, "user_api_id": user.api_id, "ci": "true"},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"exists": {"field": "ci_info"}},
                        {"term": {"user_api_id": user.api_id}},
                    ],
                }
            },
        }

    def test_list_build_by_user_and_not_ci(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "earliest": earliest_str, "user_api_id": user.api_id, "ci": "false"},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must_not": [{"exists": {"field": "ci_info"}}],
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"term": {"user_api_id": user.api_id}},
                    ],
                }
            },
        }

    def test_list_builds_with_pagination(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        u3 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        u4 = ToolchainUser.create(username="george", email="george@seinfeld.com")
        build_time = datetime.datetime(2019, 8, 22, 10, 55, 30, tzinfo=datetime.timezone.utc)
        run_infos = self._seed_dynamodb_data(repo, user, u2, u3, u4, build_time=build_time)
        DummyElasticRequests.add_search_response(run_infos[:3], override_total=42)
        response = self._get_builds(client, repo, data={"page_size": 12, "cmd_line": "Hoochie Mama", "page": 3})
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"count", "page", "results", "total_pages", "offset", "max_pages"}
        assert json_response["count"] == 42
        assert json_response["page"] == 3
        assert json_response["offset"] == 36
        assert len(json_response["results"]) == 3
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"match": {"cmd_line": "Hoochie Mama"}},
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "from": 36,
            "size": 12,
        }

    def test_list_builds_with_pagination_no_page_size(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        u3 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        u4 = ToolchainUser.create(username="george", email="george@seinfeld.com")
        build_time = datetime.datetime(2019, 8, 22, 10, 55, 30, tzinfo=datetime.timezone.utc)
        run_infos = self._seed_dynamodb_data(repo, user, u2, u3, u4, build_time=build_time)
        DummyElasticRequests.add_search_response(run_infos[:3], override_total=42)
        response = self._get_builds(client, repo, data={"page": 7})
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"count", "page", "results", "total_pages", "max_pages", "offset"}
        assert json_response["count"] == 42
        assert json_response["page"] == 7
        assert json_response["offset"] == 140
        assert len(json_response["results"]) == 3
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "from": 7 * 20,
            "size": 20,
        }

    def test_list_builds_by_pull_request(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={
                "outcome": "SUCCESS",
                "pr": "92",
                "earliest": earliest_str,
            },
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        assert json_response["count"] == 91
        build_data = json_response["results"]
        assert len(build_data) == 8
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": repo.customer_id}},
                        {"term": {"repo_id": repo.id}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"term": {"outcome": "SUCCESS"}},
                        {"term": {"ci_info.pull_request": 92}},
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 20,
        }

    def test_list_build_invalid_user_params(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "earliest": earliest_str, "user": "david", "user_api_id": user.api_id},
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "__all__": [{"message": "Specifying both user & user_api_id is not supported.", "code": "invalid"}]
            }
        }
        DummyElasticRequests.assert_no_requests()

    def test_list_build_by_username(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        user_2 = create_github_user(
            username="whatley", email="tim@jerrysplace.com", full_name="Time Whatley", github_user_id="233333"
        )
        customer.add_user(user_2)
        self._setup_multi_user_data(user_2, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "earliest": earliest_str, "user": "whatley"},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"term": {"user_api_id": user_2.api_id}},
                    ],
                }
            },
        }

    def test_list_build_user_me(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 22, "earliest": earliest_str, "user": "me"},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"term": {"user_api_id": user.api_id}},
                    ],
                }
            },
        }

    def test_list_build_user_api_id(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(client, repo, data={"page_size": 22, "earliest": earliest_str, "user": user.api_id})
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 22,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"term": {"user_api_id": user.api_id}},
                    ],
                }
            },
        }

    def test_list_build_by_title(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        self._setup_multi_user_data(user, repo)
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 30, "earliest": earliest_str, "title": "Moles — freckles’ ugly cousin", "ci": "true"},
        )
        assert response.status_code == 200
        json_response = response.json()
        assert set(json_response.keys()) == {"results", "count", "total_pages", "max_pages"}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 30,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.pk}},
                        {"term": {"repo_id": repo.pk}},
                        {"range": {"timestamp": {"format": "epoch_second", "gte": 1546385148}}},
                        {"exists": {"field": "ci_info"}},
                        {"match": {"title": "Moles — freckles’ ugly cousin"}},
                    ],
                }
            },
        }

    def test_get_builds_with_es_connection_timeout(
        self, settings, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_builds_and_users(user, repo)
        settings.DEBUG = False  # Turn off django debug mode to get the actual prod behavior for an error
        client.raise_request_exception = False
        DummyElasticRequests.add_search_network_error(ConnectionTimeout, "They are running out of shrimp")
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 30, "earliest": earliest_str, "ci": "true"},
        )
        assert response.status_code == 503
        assert response.headers["Content-Type"] == "application/json"
        assert response.json() == {"error": "transient", "error_type": "SearchTransientError"}
        DummyElasticRequests.assert_single_request()

    def test_get_builds_with_es_http_error_403(
        self, settings, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_builds_and_users(user, repo)
        settings.DEBUG = False  # Turn off django debug mode to get the actual prod behavior for an error
        client.raise_request_exception = False
        DummyElasticRequests.add_search_http_error_response(
            http_error_code=403,
            error_msg="The request signature we calculated does not match the signature you provided. Check your AWS Secret Access Key and signing method. Consult the service documentation for details.",
        )
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 30, "earliest": earliest_str, "ci": "true"},
        )
        assert (
            response.status_code == 500
        )  # TODO: this should be handled and transformed to a 503 error https://github.com/toolchainlabs/toolchain/issues/10182
        # TODO: we shouldn't be returning html for 500 errors, see: https://github.com/toolchainlabs/toolchain/issues/10166
        assert (
            response.content
            == b'\n<!doctype html>\n<html lang="en">\n<head>\n  <title>Server Error (500)</title>\n</head>\n<body>\n  <h1>Server Error (500)</h1><p></p>\n</body>\n</html>\n'
        )
        DummyElasticRequests.assert_single_request()

    def test_get_builds_with_es_http_error_429(
        self, settings, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        self._setup_builds_and_users(user, repo)
        settings.DEBUG = False  # Turn off django debug mode to get the actual prod behavior for an error
        client.raise_request_exception = False

        DummyElasticRequests.add_response(
            "GET",
            f"/{DummyElasticRequests._INDEX_NAME}/_search",
            status_code=429,
            body=b"429 Too Many Requests /buildsense/_search",
        )
        earliest = datetime.datetime(2019, 1, 1, 23, 55, 48, tzinfo=datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S")
        response = self._get_builds(
            client,
            repo,
            data={"page_size": 30, "earliest": earliest_str, "ci": "true"},
        )
        assert response.status_code == 503
        assert response.json() == {"error": "transient", "error_type": "SearchTransientError"}
        DummyElasticRequests.assert_single_request()

    def test_list_builds_invalid_runtime_min_max_values(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        response = self._get_builds(
            client,
            repo,
            data={
                "page": 1,
                "run_time_min": "99999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999",
                "run_time_max": "999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999",
            },
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "run_time_min": [
                    {"message": "Ensure this value is less than or equal to 259200.0.", "code": "max_value"}
                ],
                "run_time_max": [
                    {"message": "Ensure this value is less than or equal to 259200.0.", "code": "max_value"}
                ],
            }
        }
        DummyElasticRequests.assert_no_requests()


class TestGetBuildViewsApi(BaseTestViewsApi):
    def _get_build(self, client, repo: Repo, run_id: str, extra: dict[str, str] | None = None) -> HttpResponse:
        extra = extra or {}
        url = self._get_base_url(repo, run_id)
        return client.get(url, extra)

    def test_get_build(self, client, repo: Repo, user_no_details: ToolchainUser, customer: Customer) -> None:
        user_no_details.full_name = "Kenny Kramer"
        user_no_details.save()
        run_id, key, raw_data, run_info = self._prepare_build(repo, user_no_details)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build(client, repo, run_id)

        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "branch": "vandelay",
                "buildroot": "/Users/asher/projects/toolchain",
                "cmd_line": "pants --no-verify-config test src/python/toolchain/util/::",
                "customer_id": customer.pk,
                "machine": "Ashers-MacBook-Pro.local",
                "outcome": "SUCCESS",
                "path": "/Users/asher/projects/toolchain",
                "repo_id": repo.pk,
                "repo_slug": "acmebotid",
                "is_ci": False,
                "revision": "d45a94b63dedb8666a45ac2258c3afe5306be95a",
                "run_id": "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
                "run_time": None,
                "ci_info": None,
                "title": None,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/trace/",
                        "name": "trace",
                    },
                ],
                "build_artifacts": {},
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/",
                "user": {
                    "api_id": user_no_details.api_id,
                    "avatar_url": None,
                    "full_name": "Kenny Kramer",
                    "username": "kenny",
                },
                "version": "1.18.0rc0",
                "datetime": "2019-04-22T16:21:44+00:00",
                "specs_from_command_line": [],
                "goals": [],
            },
        }
        DummyElasticRequests.assert_single_request()

    def test_get_build_ci_pr(self, client, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_build_pr_env_end")
        fixture["run_info"]["outcome"] = "NOT_AVAILABLE"
        run_info = self._store_build(repo, user, fixture, build_time)
        assert run_info.ci_info is not None
        run_info.ci_info.link = "http://jerry.com/costanza"
        run_info.outcome = "SUCCESS"
        assert RunInfoTable.for_customer_id(repo.customer_id).update_or_insert_run(run_info) is True
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build(client, repo, run_info.run_id)
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "abbc94b856d5",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "run_id": "pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "branch": "pull/6474",
                "revision": "e25365b0ad091de0cb1580b92968755ad1675f11",
                "title": "No soup for you come back one year!",
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6474,
                    "job_name": "build",
                    "build_num": 22480.0,
                    "links": [
                        {"icon": "github", "text": "Pull request 6474", "link": "http://jerry.com/costanza"},
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22480",
                        },
                    ],
                },
                "user": {
                    "username": "kramer",
                    "full_name": "Cosmo Kramer",
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-11T15:31:56+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/trace/",
                        "name": "trace",
                    },
                ],
                "goals": ["validate"],
                "build_artifacts": {},
            }
        }
        DummyElasticRequests.assert_single_request()

    def test_get_build_staff(
        self, staff_user_client, repo: Repo, user_no_details: ToolchainUser, customer: Customer
    ) -> None:
        run_id, key, raw_data, run_info = self._prepare_build(repo, user_no_details)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build(staff_user_client, repo, run_id)

        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "branch": "vandelay",
                "buildroot": "/Users/asher/projects/toolchain",
                "cmd_line": "pants --no-verify-config test src/python/toolchain/util/::",
                "customer_id": customer.pk,
                "machine": "Ashers-MacBook-Pro.local",
                "outcome": "SUCCESS",
                "path": "/Users/asher/projects/toolchain",
                "repo_id": repo.pk,
                "repo_slug": "acmebotid",
                "is_ci": False,
                "revision": "d45a94b63dedb8666a45ac2258c3afe5306be95a",
                "run_id": "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
                "run_time": None,
                "ci_info": None,
                "title": None,
                "build_artifacts": {},
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/",
                "user": {
                    "api_id": user_no_details.api_id,
                    "avatar_url": None,
                    "full_name": "kenny",
                    "username": "kenny",
                },
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/trace/",
                        "name": "trace",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/raw/",
                        "name": "raw",
                    },
                ],
                "version": "1.18.0rc0",
                "datetime": "2019-04-22T16:21:44+00:00",
                "specs_from_command_line": [],
                "goals": [],
            },
        }
        DummyElasticRequests.assert_single_request()

    def test_get_build_with_impersonation(self, settings, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        admin = create_staff(username="bob", email="bob@jerrysplace.com", github_user_id="909090")
        client = self._get_client_for_user(user=user, settings=settings, impersonator=admin)
        run_id, key, raw_data, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build(client, repo, run_id)
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "branch": "vandelay",
                "buildroot": "/Users/asher/projects/toolchain",
                "cmd_line": "pants --no-verify-config test src/python/toolchain/util/::",
                "customer_id": customer.pk,
                "machine": "Ashers-MacBook-Pro.local",
                "outcome": "SUCCESS",
                "path": "/Users/asher/projects/toolchain",
                "repo_id": repo.pk,
                "repo_slug": "acmebotid",
                "is_ci": False,
                "revision": "d45a94b63dedb8666a45ac2258c3afe5306be95a",
                "run_id": "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
                "run_time": None,
                "ci_info": None,
                "title": None,
                "build_artifacts": {},
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/trace/",
                        "name": "trace",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/raw/",
                        "name": "raw",
                    },
                ],
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/",
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "version": "1.18.0rc0",
                "datetime": "2019-04-22T16:21:44+00:00",
                "specs_from_command_line": [],
                "goals": [],
            },
        }
        DummyElasticRequests.assert_single_request()

    def test_get_build_other_user_denied(self, settings, repo: Repo, user: ToolchainUser) -> None:
        other_user = create_github_user(username="pinkman", email="jesse@breakingbad.com", github_user_id="999939")
        run_id, _, _, _ = self._prepare_build(repo, user)
        client = self._get_client_for_user(other_user, settings)
        response = self._get_build(client, repo, run_id)
        # We hide/404 the repo since other user doesn't have access to it.
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_get_non_existing_build_without_user_id(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        self._seed_dynamodb_data(repo, user)
        DummyElasticRequests.add_empty_search_response()
        response = self._get_build(client, repo, "no_soup_for_you")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_non_existing_build_with_user_id(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        self._seed_dynamodb_data(repo, user)
        response = self._get_build(client, repo, "no_soup_for_you", {"user_api_id": user.api_id})
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_build_other_user(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        build_user = create_github_user(
            username="whatley", email="tim.whatley@breakingbad.com", full_name="Tim Whatley", github_username="dentist"
        )
        run_id, key, raw_data, _ = self._prepare_build(repo, build_user)
        response = self._get_build(client, repo, run_id, {"user_api_id": build_user.api_id})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "branch": "vandelay",
                "buildroot": "/Users/asher/projects/toolchain",
                "cmd_line": "pants --no-verify-config test src/python/toolchain/util/::",
                "customer_id": customer.pk,
                "machine": "Ashers-MacBook-Pro.local",
                "outcome": "SUCCESS",
                "path": "/Users/asher/projects/toolchain",
                "repo_id": repo.pk,
                "repo_slug": "acmebotid",
                "is_ci": False,
                "revision": "d45a94b63dedb8666a45ac2258c3afe5306be95a",
                "run_id": "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
                "run_time": None,
                "ci_info": None,
                "title": None,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/trace/",
                        "name": "trace",
                    },
                ],
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/",
                "build_artifacts": {},
                "user": {
                    "api_id": build_user.api_id,
                    "avatar_url": "https://pictures.jerry.com/dentist",
                    "full_name": "Tim Whatley",
                    "username": "whatley",
                },
                "version": "1.18.0rc0",
                "datetime": "2019-04-22T16:21:44+00:00",
                "specs_from_command_line": [],
                "goals": [],
            },
        }

    def test_get_build_me(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        run_id, key, raw_data, _ = self._prepare_build(repo, user)
        response = self._get_build(client, repo, run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "branch": "vandelay",
                "buildroot": "/Users/asher/projects/toolchain",
                "cmd_line": "pants --no-verify-config test src/python/toolchain/util/::",
                "customer_id": customer.pk,
                "machine": "Ashers-MacBook-Pro.local",
                "outcome": "SUCCESS",
                "path": "/Users/asher/projects/toolchain",
                "repo_id": repo.pk,
                "repo_slug": "acmebotid",
                "is_ci": False,
                "revision": "d45a94b63dedb8666a45ac2258c3afe5306be95a",
                "run_id": "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
                "run_time": None,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/trace/",
                        "name": "trace",
                    },
                ],
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585/",
                "build_artifacts": {},
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "version": "1.18.0rc0",
                "ci_info": None,
                "title": None,
                "datetime": "2019-04-22T16:21:44+00:00",
                "specs_from_command_line": [],
                "goals": [],
            },
        }

    def test_get_ci_build(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        run_id = self._store_build(repo, user, load_fixture("ci_build_pr_final_1")).run_id
        response = self._get_build(client, repo, run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "branch": "pull/6490",
                "buildroot": "/home/toolchain/project",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "customer_id": customer.pk,
                "machine": "c2fd5769a378",
                "outcome": "SUCCESS",
                "path": "/home/toolchain/project",
                "repo_id": repo.pk,
                "repo_slug": "acmebotid",
                "is_ci": True,
                "revision": "c5454b4327903b7d2242f705e9218ca90bcc7e49",
                "run_id": "pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427",
                "run_time": None,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/trace/",
                        "name": "trace",
                    },
                ],
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/",
                "build_artifacts": {},
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "version": "2.0.0.dev6",
                "title": "No soup for you come back one year!",
                "ci_info": {
                    "build_num": 22579.0,
                    "job_name": "build",
                    "pull_request": 6490,
                    "run_type": "pull_request",
                    "username": "asherf",
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22579",
                        }
                    ],
                },
                "datetime": "2020-08-13T00:21:00+00:00",
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "goals": ["validate"],
            },
        }

    def test_get_running_build(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer):
        build_data = load_fixture("ci_build_pr_start_2")
        build_time = utcnow() - datetime.timedelta(minutes=1)
        run_info = self._store_build(repo, user, build_data, build_time=build_time)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "c2fd5769a378",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "RUNNING",
                "cmd_line": "pants --pants-bin-name=./pants --tag=-nolint lint prod/python:: src/python::",
                "run_id": "pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "build_artifacts": {},
                "run_time": None,
                "branch": None,
                "revision": None,
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/workunits/",
                        "name": "workunits",
                    },
                ],
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6490,
                    "job_name": "build",
                    "build_num": 22579.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22579",
                        }
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-13T00:21:45+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
                "is_ci": True,
                "goals": ["lint"],
            }
        }

    def test_get_running_build_expired(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer):
        build_data = load_fixture("ci_build_pr_start_2")
        build_time = utcnow() - datetime.timedelta(minutes=10)
        run_info = self._store_build(repo, user, build_data, build_time=build_time)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "c2fd5769a378",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "TIMEOUT",
                "cmd_line": "pants --pants-bin-name=./pants --tag=-nolint lint prod/python:: src/python::",
                "run_id": "pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "branch": None,
                "revision": None,
                "build_artifacts": {},
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/workunits/",
                        "name": "workunits",
                    },
                ],
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6490,
                    "job_name": "build",
                    "build_num": 22579.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22579",
                        }
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-13T00:21:45+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
                "is_ci": True,
                "goals": ["lint"],
            }
        }

    def test_get_build_with_artifacts(self, client, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_build_pr_env_end")
        run_info = self._store_build(repo, user, fixture, build_time=build_time)
        add_build_artifacts(repo, user, run_info.run_id, add_log=False, artifacts={"jerry.json": None}, runtime=60001)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "abbc94b856d5",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "run_id": "pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "branch": "pull/6474",
                "revision": "e25365b0ad091de0cb1580b92968755ad1675f11",
                "title": "No soup for you come back one year!",
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6474,
                    "job_name": "build",
                    "build_num": 22480.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22480",
                        }
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-11T15:31:56+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "goals": ["validate"],
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/trace/",
                        "name": "trace",
                    },
                ],
                "build_artifacts": {
                    "test": {
                        "type": "goal",
                        "artifacts": [
                            {
                                "name": "jerry.json",
                                "description": "Run Pytest",
                                "run_time_msec": 60001,
                                "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                                "content_types": ["text/plain"],
                            }
                        ],
                    }
                },
            },
        }

    def test_get_build_with_artifacts_and_log(
        self, client, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_build_pr_env_end")
        run_info = self._store_build(repo, user, fixture, build_time=build_time)
        add_build_artifacts(repo, user, run_info.run_id, add_log=True, artifacts={"jerry.json": None}, runtime=890909)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "abbc94b856d5",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "run_id": "pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "branch": "pull/6474",
                "revision": "e25365b0ad091de0cb1580b92968755ad1675f11",
                "title": "No soup for you come back one year!",
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6474,
                    "job_name": "build",
                    "build_num": 22480.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22480",
                        }
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-11T15:31:56+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/trace/",
                        "name": "trace",
                    },
                ],
                "goals": ["validate"],
                "build_artifacts": {
                    "test": {
                        "type": "goal",
                        "artifacts": [
                            {
                                "name": "jerry.json",
                                "description": "Run Pytest",
                                "run_time_msec": 890909,
                                "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                                "content_types": ["text/plain"],
                            }
                        ],
                    },
                    "logs": {
                        "type": "run",
                        "artifacts": [{"name": "pants_run_log.txt", "description": "Pants run log", "group": "Logs"}],
                    },
                },
            }
        }

    def test_get_build_with_artifacts_logs_and_options(
        self, client, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_build_pr_env_end")
        run_info = self._store_build(repo, user, fixture, build_time=build_time)
        add_build_artifacts(
            repo,
            user,
            run_info.run_id,
            add_log=True,
            artifacts={"jerry.json": None},
            add_options=True,
            build_stats=fixture,
            runtime=77788,
        )
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "abbc94b856d5",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "run_id": "pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "branch": "pull/6474",
                "revision": "e25365b0ad091de0cb1580b92968755ad1675f11",
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/trace/",
                        "name": "trace",
                    },
                ],
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6474,
                    "job_name": "build",
                    "build_num": 22480.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22480",
                        }
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-11T15:31:56+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "goals": ["validate"],
                "build_artifacts": {
                    "test": {
                        "type": "goal",
                        "artifacts": [
                            {
                                "name": "jerry.json",
                                "description": "Run Pytest",
                                "run_time_msec": 77788,
                                "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                                "content_types": ["text/plain"],
                            }
                        ],
                    },
                    "logs": {
                        "type": "run",
                        "artifacts": [{"name": "pants_run_log.txt", "description": "Pants run log", "group": "Logs"}],
                    },
                    "pants_options": {
                        "type": "run",
                        "name": "Pants Options",
                        "artifacts": [
                            {
                                "name": "pants_options.json",
                                "description": "Pants Options",
                                "group": "pants_options",
                                "content_types": ["pants_options"],
                            }
                        ],
                    },
                },
            }
        }

    def test_get_build_with_artifacts_with_results(
        self, client, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_build_pr_env_end")
        run_info = self._store_build(repo, user, fixture, build_time=build_time)
        artifacts = OrderedDict(
            (("newman.json", None), ("jerry.json", "SUCCESS"), ("george.json", None), ("kramer.json", "FAILURE"))
        )
        add_build_artifacts(repo, user, run_info.run_id, add_log=False, artifacts=artifacts)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        json_response = response.json()
        build_artifacts = json_response["run_info"].pop("build_artifacts")
        assert build_artifacts == {
            "test": {
                "type": "goal",
                "artifacts": [
                    {
                        "name": "newman.json",
                        "description": "Run Pytest",
                        "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                        "content_types": ["text/plain"],
                    },
                    {
                        "name": "jerry.json",
                        "description": "Run Pytest",
                        "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                        "result": "SUCCESS",
                        "content_types": ["text/plain"],
                    },
                    {
                        "name": "george.json",
                        "description": "Run Pytest",
                        "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                        "content_types": ["text/plain"],
                    },
                    {
                        "name": "kramer.json",
                        "description": "Run Pytest",
                        "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                        "content_types": ["text/plain"],
                        "result": "FAILURE",
                    },
                ],
            }
        }
        assert json_response == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "abbc94b856d5",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "run_id": "pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "branch": "pull/6474",
                "revision": "e25365b0ad091de0cb1580b92968755ad1675f11",
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/trace/",
                        "name": "trace",
                    },
                ],
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6474,
                    "job_name": "build",
                    "build_num": 22480.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22480",
                        }
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-11T15:31:56+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "goals": ["validate"],
            }
        }

    def test_get_build_with_run_goal(self, client, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_pr_pants_run")
        run_info = self._store_build(repo, user, fixture, build_time=build_time, add_scm_link=ScmProvider.GITHUB)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "a97e923e5586 [docker]",
                "version": "2.2.0rc1",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants --pants-version=2.2.0rc1 run src/python/toolchain/service/toolshed:toolshed-manage -- migrate_all",
                "run_id": "pants_run_2021_01_11_16_00_51_486_9f76c21503d64df18aea5a596e057448",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["src/python/toolchain/service/toolshed:toolshed-manage"],
                "run_time": None,
                "branch": "pull/8027",
                "revision": "422588c3899dad7abe56cf6e96e015cdae2737e8",
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2021_01_11_16_00_51_486_9f76c21503d64df18aea5a596e057448/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2021_01_11_16_00_51_486_9f76c21503d64df18aea5a596e057448/trace/",
                        "name": "trace",
                    },
                ],
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 8027,
                    "job_name": "build-with-pants",
                    "build_num": 48925.0,
                    "links": [
                        {
                            "icon": "github",
                            "text": "Pull request 8027",
                            "link": "https://github.com/toolchainlabs/toolchain/",
                        },
                        {
                            "icon": "circleci",
                            "text": "build-with-pants",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/48925",
                        },
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2021-01-11T16:00:51+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2021_01_11_16_00_51_486_9f76c21503d64df18aea5a596e057448/",
                "is_ci": True,
                "goals": ["run toolshed-manage"],
                "build_artifacts": {},
            }
        }

    def test_get_build_from_travis_run(self, client, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("travis_ci_build_pr_final_1")
        run_info = self._store_build(repo, user, fixture, build_time=build_time, add_scm_link=ScmProvider.GITHUB)
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/travis/build/toolchainlabs/example-python",
                "machine": "travis-job-104661f0-8fbf-47b4-bc37-8803f9dd0d5d",
                "version": "2.0.0a3",
                "path": "/home/travis/build/toolchainlabs/example-python",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants --pants-version=2.0.0a3 setup-py --args=bdist_wheel helloworld/util:dist",
                "run_id": "pants_run_2020_09_14_22_49_09_208_686cbb2fd6c14a8c9e7b843e7a1f6c90",
                "customer_id": customer.id,
                "specs_from_command_line": ["helloworld/util:dist"],
                "run_time": None,
                "branch": "4886bc63fe1c270be4e93308fcda04755142256a",
                "revision": "4886bc63fe1c270be4e93308fcda04755142256a",
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_09_14_22_49_09_208_686cbb2fd6c14a8c9e7b843e7a1f6c90/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_09_14_22_49_09_208_686cbb2fd6c14a8c9e7b843e7a1f6c90/trace/",
                        "name": "trace",
                    },
                ],
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 14,
                    "job_name": "I call it golden boy",
                    "build_num": 86.0,
                    "links": [
                        {
                            "icon": "github",
                            "text": "Pull request 14",
                            "link": "https://github.com/toolchainlabs/toolchain/",
                        },
                        {
                            "icon": "travis",
                            "text": "I call it golden boy",
                            "link": "https://travis-ci.com/toolchainlabs/example-python/builds/184295888",
                        },
                    ],
                },
                "user": {
                    "api_id": user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                    "full_name": "Cosmo Kramer",
                    "username": "kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-09-14T22:49:09+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "goals": ["setup-py"],
                "build_artifacts": {},
            }
        }

    def test_get_build_inactive_user(self, client, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        build_user = create_github_user(
            username="jerry", email="jerry@jerrysplace.com", full_name="Jerry Seinfeld", github_user_id="88339"
        )
        customer.add_user(build_user)
        build_time = datetime.datetime(2020, 10, 3, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("ci_build_pr_env_end")
        run_info = self._store_build(repo, build_user, fixture, build_time=build_time)
        build_user.deactivate()
        response = self._get_build(client, repo, run_info.run_id, extra={"user_api_id": build_user.api_id})
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/home/toolchain/project",
                "machine": "abbc94b856d5",
                "version": "2.0.0.dev6",
                "path": "/home/toolchain/project",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants validate prod/python:: src/python::",
                "run_id": "pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["prod/python::", "src/python::"],
                "run_time": None,
                "download_links": [
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/trace/",
                        "name": "trace",
                    },
                ],
                "branch": "pull/6474",
                "revision": "e25365b0ad091de0cb1580b92968755ad1675f11",
                "title": "No soup for you come back one year!",
                "build_artifacts": {},
                "ci_info": {
                    "username": "asherf",
                    "run_type": "pull_request",
                    "pull_request": 6474,
                    "job_name": "build",
                    "build_num": 22480.0,
                    "links": [
                        {
                            "icon": "circleci",
                            "text": "build",
                            "link": "https://circleci.com/gh/toolchainlabs/toolchain/22480",
                        }
                    ],
                },
                "user": {
                    "username": "jerry",
                    "full_name": "Jerry Seinfeld",
                    "api_id": build_user.api_id,
                    "avatar_url": "https://pictures.jerry.com/gh-jerry",
                },
                "repo_slug": "acmebotid",
                "datetime": "2020-08-11T15:31:56+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/{run_info.run_id}/",
                "is_ci": True,
                "goals": ["validate"],
            }
        }

    def test_get_build_bitbucket_pipelines(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="moles", name="Moles", scm=Customer.Scm.BITBUCKET)
        repo = Repo.create("festivus", customer=customer, name="Festivus for the rest of us")
        customer.add_user(user)
        build_time = datetime.datetime(2021, 8, 12, 16, 0, 0, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("bitbucket_pr_lint_run")
        run_info = self._store_build(repo, user, fixture, build_time=build_time, add_scm_link=ScmProvider.BITBUCKET)
        response = self._get_build(client, repo=repo, run_id=run_info.run_id, extra={"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/opt/atlassian/pipelines/agent/build",
                "machine": "aa13f106-c64d-41c6-b68c-5fe26f04bd00-qf5cx",
                "version": "2.6.0",
                "path": "/opt/atlassian/pipelines/agent/build",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants --pants-version=2.6.0 lint ::",
                "run_id": "pants_run_2021_08_11_00_11_30_828_66be5f4f9775442d8b4bd3b9dbb50e55",
                "customer_id": customer.id,
                "specs_from_command_line": ["::"],
                "run_time": None,
                "branch": "upgrades",
                "revision": "60741389c6e2cb4006795dbbb6bb8c0a1acb2576",
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/moles/festivus/builds/pants_run_2021_08_11_00_11_30_828_66be5f4f9775442d8b4bd3b9dbb50e55/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/moles/festivus/builds/pants_run_2021_08_11_00_11_30_828_66be5f4f9775442d8b4bd3b9dbb50e55/trace/",
                        "name": "trace",
                    },
                ],
                "ci_info": {
                    "username": None,
                    "run_type": "pull_request",
                    "pull_request": 11,
                    "job_name": "Bitbucket pipeline job",
                    "build_num": 29.0,
                    "links": [
                        {
                            "icon": "bitbucket",
                            "text": "Pull request 11",
                            "link": "https://bitbucket.org/festivus-miracle/minimal-pants/src/main/",
                        },
                        {
                            "icon": "bitbucket",
                            "text": "Bitbucket pipeline job",
                            "link": "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/29/steps/%7Baa13f106-c64d-41c6-b68c-5fe26f04bd00%7D",
                        },
                    ],
                },
                "user": {
                    "username": "kramer",
                    "api_id": user.api_id,
                    "full_name": "Cosmo Kramer",
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                },
                "repo_slug": "festivus",
                "datetime": "2021-08-11T00:11:29+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2021_08_11_00_11_30_828_66be5f4f9775442d8b4bd3b9dbb50e55/",
                "is_ci": True,
                "goals": ["lint"],
                "build_artifacts": {},
            }
        }

    def test_get_build_bitbucket_pipelines_on_tag(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="moles", name="Moles", scm=Customer.Scm.BITBUCKET)
        repo = Repo.create("festivus", customer=customer, name="Festivus for the rest of us")
        customer.add_user(user)
        build_time = datetime.datetime(2021, 8, 12, 16, 0, 0, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("bitbucket_tag_lint_run")
        run_info = self._store_build(repo, user, fixture, build_time=build_time, add_scm_link=ScmProvider.BITBUCKET)
        response = self._get_build(client, repo=repo, run_id=run_info.run_id, extra={"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/opt/atlassian/pipelines/agent/build",
                "machine": "f987bb55-e706-49f5-9a2d-6ade1f16ee5f-l4lcq",
                "version": "2.6.0",
                "path": "/opt/atlassian/pipelines/agent/build",
                "outcome": "SUCCESS",
                "cmd_line": "pants --pants-bin-name=./pants --pants-version=2.6.0 lint ::",
                "run_id": "pants_run_2021_08_12_00_53_51_617_f8c6c6871059495ebaef93fb4f3b394f",
                "customer_id": customer.id,
                "specs_from_command_line": ["::"],
                "run_time": None,
                "branch": "113feb0671944c44d274fc4d7c32c681427f9011",
                "revision": "113feb0671944c44d274fc4d7c32c681427f9011",
                "title": "No soup for you come back one year!",
                "download_links": [
                    {
                        "link": "/api/v1/repos/moles/festivus/builds/pants_run_2021_08_12_00_53_51_617_f8c6c6871059495ebaef93fb4f3b394f/workunits/",
                        "name": "workunits",
                    },
                    {
                        "link": "/api/v1/repos/moles/festivus/builds/pants_run_2021_08_12_00_53_51_617_f8c6c6871059495ebaef93fb4f3b394f/trace/",
                        "name": "trace",
                    },
                ],
                "ci_info": {
                    "username": None,
                    "run_type": "tag",
                    "pull_request": None,
                    "job_name": "Bitbucket pipeline job",
                    "build_num": 33.0,
                    "links": [
                        {
                            "icon": "bitbucket",
                            "text": "Tag/Release",
                            "link": "https://bitbucket.org/festivus-miracle/minimal-pants/src/main/",
                        },
                        {
                            "icon": "bitbucket",
                            "text": "Bitbucket pipeline job",
                            "link": "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/33/steps/%7Bf987bb55-e706-49f5-9a2d-6ade1f16ee5f%7D",
                        },
                    ],
                },
                "user": {
                    "username": "kramer",
                    "api_id": user.api_id,
                    "full_name": "Cosmo Kramer",
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                },
                "repo_slug": "festivus",
                "datetime": "2021-08-12T00:53:48+00:00",
                "link": f"/api/v1/repos/{customer.slug}/{repo.slug}/builds/pants_run_2021_08_12_00_53_51_617_f8c6c6871059495ebaef93fb4f3b394f/",
                "is_ci": True,
                "goals": ["lint"],
                "build_artifacts": {},
            }
        }

    def test_get_build_with_platform_info(self, client, repo: Repo, user: ToolchainUser) -> None:
        build_time = datetime.datetime(2022, 3, 27, 19, 24, 44, tzinfo=datetime.timezone.utc)
        fixture = load_fixture("go_lint_pants_runs")
        run_info = self._store_build(repo, user, fixture, build_time=build_time)
        add_build_artifacts(repo, user, run_info.run_id, add_log=False, artifacts={"jerry.json": None})
        response = self._get_build(client, repo, run_info.run_id, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == {
            "run_info": {
                "repo_id": repo.id,
                "buildroot": "/Users/asher/projects/toolchain",
                "machine": "Ashers-MacBook-Pro.local",
                "version": "2.10.0rc1",
                "path": "/Users/asher/projects/toolchain",
                "outcome": "FAILURE",
                "cmd_line": "pants --pants-bin-name=./pants --pants-version=2.10.0rc1 lint src/go/src/toolchain/::",
                "run_id": "pants_run_2022_02_15_15_16_10_407_d5d72bb53df54f389f3a216d4ff0826f",
                "customer_id": repo.customer_id,
                "specs_from_command_line": ["src/go/src/toolchain::"],
                "run_time": None,
                "branch": "benes",
                "revision": "97351335d19736b2a6e09327a1ae3844e69da940",
                "title": None,
                "ci_info": None,
                "user": {
                    "username": "kramer",
                    "api_id": user.api_id,
                    "full_name": "Cosmo Kramer",
                    "avatar_url": "https://pictures.jerry.com/gh-kramer",
                },
                "repo_slug": "acmebotid",
                "datetime": "2022-02-15T20:16:09+00:00",
                "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2022_02_15_15_16_10_407_d5d72bb53df54f389f3a216d4ff0826f/",
                "is_ci": False,
                "goals": ["lint"],
                "platform": {
                    "architecture": "x86_64",
                    "cpu_count": 12,
                    "mem_bytes": 17179869184,
                    "os": "Darwin",
                    "os_release": "21.3.0",
                    "processor": "i386",
                    "python_implementation": "CPython",
                    "python_version": "3.8.12",
                },
                "build_artifacts": {
                    "test": {
                        "type": "goal",
                        "artifacts": [
                            {
                                "name": "jerry.json",
                                "description": "Run Pytest",
                                "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                                "content_types": ["text/plain"],
                            }
                        ],
                    }
                },
                "download_links": [
                    {
                        "name": "workunits",
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2022_02_15_15_16_10_407_d5d72bb53df54f389f3a216d4ff0826f/workunits/",
                    },
                    {
                        "name": "trace",
                        "link": "/api/v1/repos/acmeid/acmebotid/builds/pants_run_2022_02_15_15_16_10_407_d5d72bb53df54f389f3a216d4ff0826f/trace/",
                    },
                ],
            }
        }

    def test_get_build_search_network_error(self, client, repo: Repo, user_no_details: ToolchainUser) -> None:
        user_no_details.full_name = "Kenny Kramer"
        user_no_details.save()
        run_id, *_ = self._prepare_build(repo, user_no_details)
        DummyElasticRequests.add_search_network_error(ConnectionTimeout, "They are running out of shrimp")
        response = self._get_build(client, repo, run_id)
        assert response.status_code == 503
        assert response.json() == {"error": "transient", "error_type": "SearchTransientError"}


class TestOptionsViewsApi(BaseTestViewsApi):
    def _get_options(self, client, repo: Repo, **kwargs) -> HttpResponse:
        url = self._get_base_url(repo)
        extra = dict(QUERY_STRING=urlencode(kwargs, doseq=True)) if kwargs else {}
        return client.options(url, **extra)

    def _setup_users(self, customer: Customer) -> tuple[str, ...]:
        u1 = create_github_user(
            username="jerry", email="jerry@newyork.com", full_name="Jerry Seinfeld", github_user_id="34412"
        )
        u2 = create_github_user(
            username="cosmo", email="kramer@newyork.com", full_name="Cosmo Kramer", github_user_id="55411"
        )
        u3 = create_github_user(
            username="george", email="costanza@newyork.com", full_name="George Costanza", github_user_id="22255"
        )
        u4 = create_github_user(
            username="elaine", email="elaine@newyork.com", full_name="Elaine Benes", github_user_id="9901"
        )
        customer.add_user(u1)
        customer.add_user(u2)
        customer.add_user(u3)
        # Not adding u4 to customer on purpose
        return u1.api_id, u2.api_id, u3.api_id, u4.api_id

    def test_get_values_branch(self, client: APIClient, repo: Repo) -> None:
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("branch", ["ovaltine", "bosco", "gold"]),)
        )
        response = self._get_options(client, repo, field="branch")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "branch": {"values": ["ovaltine", "bosco", "gold"]},
        }
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_goals(self, client: APIClient, repo: Repo) -> None:
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("goals", ["old", "man", "leland"]),)
        )
        response = self._get_options(client, repo, field="goals")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "goals": {"values": ["old", "man", "leland"]},
        }
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_users_without_current_user(self, client: APIClient, repo: Repo, customer: Customer) -> None:
        u1, u2, u3, u4 = user_api_ids = self._setup_users(customer)
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(index="buildsense", results=(("user_api_id", user_api_ids),))
        response = self._get_options(client, repo, field="user_api_id")
        assert response.status_code == 200
        json_response = response.json()
        expected_users_json = [
            {
                "api_id": u4,
                "avatar_url": "https://pictures.jerry.com/gh-elaine",
                "full_name": "Elaine Benes",
                "username": "elaine",
            },
            {
                "username": "george",
                "full_name": "George Costanza",
                "api_id": u3,
                "avatar_url": "https://pictures.jerry.com/gh-george",
            },
            {
                "username": "cosmo",
                "full_name": "Cosmo Kramer",
                "api_id": u2,
                "avatar_url": "https://pictures.jerry.com/gh-cosmo",
            },
            {
                "username": "jerry",
                "full_name": "Jerry Seinfeld",
                "api_id": u1,
                "avatar_url": "https://pictures.jerry.com/gh-jerry",
            },
        ]
        assert json_response == {
            "user_api_id": {"values": expected_users_json},
        }
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_users_with_current_user(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        u1, u2, u3, u4 = self._setup_users(customer)
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("user_api_id", (u1, u2, user.api_id, u4)),)
        )
        response = self._get_options(client, repo, field="user_api_id")
        assert response.status_code == 200
        json_response = response.json()
        expected_users_json = self._get_expected_users_json(user, u1, u2, u4)
        assert json_response == {
            "user_api_id": {"values": expected_users_json},
        }
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_missing_field(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        response = self._get_options(client, repo)
        assert response.status_code == 400
        assert response.json() == {"errors": [{"code": "missing", "message": "Missing 'field'"}]}
        DummyElasticRequests.assert_no_requests()

    def test_get_values_unused_field(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        response = self._get_options(client, repo, field="branch", jerry="hello")
        assert response.status_code == 400
        assert response.json() == {"errors": [{"code": "invalid", "message": "Unused query parameters"}]}
        DummyElasticRequests.assert_no_requests()

    def test_get_values_invalid_field(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        response = self._get_options(client, repo, field="cmd_line")
        assert response.status_code == 400
        assert response.json() == {"errors": [{"code": "invalid", "message": "Invalid field value"}]}
        DummyElasticRequests.assert_no_requests()

    def test_get_values_values_for_users(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        u1, u2, u3, u4 = self._setup_users(customer)
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(index="buildsense", results=(("user_api_id", tuple()),))
        response = self._get_options(client, repo, field="user_api_id")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {"user_api_id": {"values": []}}
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_no_builds(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=0)
        DummyElasticRequests.add_aggregation_response(index="buildsense", results=(("user_api_id", tuple()),))
        response = self._get_options(client, repo, field="user_api_id")
        assert response.status_code == 200
        assert response.json() == {
            "status": "no_builds",
            "docs": "https://docs.toolchain.com/docs/getting-started-with-toolchain#configure-pants-to-use-toolchain",
        }
        assert len(DummyElasticRequests.get_requests()) == 1

    def _get_expected_users_json(self, user: ToolchainUser, u1: str, u2: str, u4: str) -> list[dict]:
        return [
            {
                "api_id": user.api_id,
                "avatar_url": "https://pictures.jerry.com/gh-kramer",
                "full_name": "Cosmo Kramer",
                "username": "kramer",
            },
            {
                "api_id": u4,
                "avatar_url": "https://pictures.jerry.com/gh-elaine",
                "full_name": "Elaine Benes",
                "username": "elaine",
            },
            {
                "username": "cosmo",
                "full_name": "Cosmo Kramer",
                "api_id": u2,
                "avatar_url": "https://pictures.jerry.com/gh-cosmo",
            },
            {
                "username": "jerry",
                "full_name": "Jerry Seinfeld",
                "api_id": u1,
                "avatar_url": "https://pictures.jerry.com/gh-jerry",
            },
        ]

    def test_get_values_users_all_users(self, settings, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        u1, u2, u3, u4 = self._setup_users(customer)
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("user_api_id", (user.api_id, u1, u2, u4)),)
        )
        user_2 = ToolchainUser.get_by_api_id(u2)
        client = self._get_client_for_user(user_2, settings)
        response = self._get_options(client, repo, field="user_api_id")
        assert response.status_code == 200
        json_response = response.json()
        expected_users_json = [
            {
                "username": "cosmo",
                "full_name": "Cosmo Kramer",
                "api_id": u2,
                "avatar_url": "https://pictures.jerry.com/gh-cosmo",
            },
            {
                "api_id": u4,
                "avatar_url": "https://pictures.jerry.com/gh-elaine",
                "full_name": "Elaine Benes",
                "username": "elaine",
            },
            {
                "username": "jerry",
                "full_name": "Jerry Seinfeld",
                "api_id": u1,
                "avatar_url": "https://pictures.jerry.com/gh-jerry",
            },
            {
                "api_id": user.api_id,
                "avatar_url": "https://pictures.jerry.com/gh-kramer",
                "full_name": "Cosmo Kramer",
                "username": "kramer",
            },
        ]
        assert json_response == {
            "user_api_id": {"values": expected_users_json},
        }
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_pull_request(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("pr", [8887771, 33333, 6666666, 222222, 1111111]),)
        )
        response = self._get_options(client, repo, field="pr")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "pr": {"values": ["8887771", "33333", "6666666", "222222", "1111111"]},
        }
        assert len(DummyElasticRequests.get_requests()) == 2

    def test_get_values_multiple_fields(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        u1, u2, u3, u4 = self._setup_users(customer)
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        DummyElasticRequests.add_aggregation_response(
            index="buildsense",
            results=(("pr", [8887771, 33333, 6666666, 222222, 1111111]), ("user_api_id", (user.api_id, u1, u2, u4))),
        )

        response = self._get_options(client, repo, field="pr,user_api_id")
        assert response.status_code == 200
        json_response = response.json()
        expected_users_json = self._get_expected_users_json(user, u1, u2, u4)
        assert json_response == {
            "pr": {"values": ["8887771", "33333", "6666666", "222222", "1111111"]},
            "user_api_id": {"values": expected_users_json},
        }
        assert len(DummyElasticRequests.get_requests()) == 2
        search_request = DummyElasticRequests.get_requests()[-1].get_json_body()
        from_time = search_request["query"]["bool"]["must"][-1]["range"]["timestamp"].pop("gte")
        assert (utcnow() - datetime.timedelta(days=30)).timestamp() == pytest.approx(from_time)

        assert search_request == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer.id}},
                        {"term": {"repo_id": repo.id}},
                        {"range": {"timestamp": {"format": "epoch_second"}}},
                    ]
                }
            },
            "aggs": {
                "pr": {"terms": {"field": "ci_info.pull_request"}},
                "user_api_id": {"terms": {"field": "user_api_id"}},
            },
            "size": 0,
        }


class TestGetBuildExtraApi(BaseTestViewsApi):
    @pytest.fixture()
    def mock_metrics_store(self):
        with mock_rest_client() as mock_client:
            yield mock_client

    def _get_build_extra(
        self, client, repo: Repo | str, run_id: str, part: str, extra: dict[str, str] | None = None
    ) -> HttpResponse:
        url = f"{self._get_base_url(repo, run_id=run_id)}{part}/"
        return client.get(url, extra or {})

    def _get_indicators(self, client, repo: Repo, params: dict | None = None, **kwargs) -> HttpResponse:
        extra = dict(QUERY_STRING=urlencode(kwargs, doseq=True)) if kwargs else {}
        url = f"{self._get_base_url(repo)}indicators/"
        return client.get(url, params, **extra) if params else client.get(url, **extra)

    def test_get_indicators(self, client: APIClient, mock_metrics_store, repo: Repo) -> None:
        add_hit_fractions_query_response(mock_metrics_store)
        add_sums_query_response(mock_metrics_store)
        response = self._get_indicators(client, repo)
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "indicators": {
                "hit_fraction": 0.7867914,
                "hit_fraction_local": 0.8142682222222222,
                "hits": 7787.0,
                "saved_cpu_time": 3373994.0,
                "saved_cpu_time_local": 3258133.0,
                "saved_cpu_time_remote": 0.0,
                "total": 12367.0,
            }
        }
        assert len(mock_metrics_store.get_requests()) == 2

    def test_get_indicators_missing_bucket(self, client: APIClient, mock_metrics_store, repo: Repo) -> None:
        mock_metrics_store.add_missing_bucket_query_response("acmeid/acmebotid")
        response = self._get_indicators(client, repo)
        assert response.status_code == 404
        assert len(mock_metrics_store.get_requests()) == 1

    def test_get_indicators_with_filters(
        self, client: APIClient, mock_metrics_store, repo: Repo, user: ToolchainUser
    ) -> None:
        add_hit_fractions_query_response(mock_metrics_store)
        add_sums_query_response(mock_metrics_store)
        response = self._get_indicators(client, repo, params={"ci": "1", "goals": "fmt,bob,jerry"})
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "indicators": {
                "hit_fraction": 0.7867914,
                "hit_fraction_local": 0.8142682222222222,
                "hits": 7787.0,
                "saved_cpu_time": 3373994.0,
                "saved_cpu_time_local": 3258133.0,
                "saved_cpu_time_remote": 0.0,
                "total": 12367.0,
            }
        }
        assert len(mock_metrics_store.get_requests()) == 2

    def test_get_indicators_with_invalid_filters(
        self, client: APIClient, mock_metrics_store, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        mock_metrics_store.add_missing_bucket_query_response("acmeid/acmebotid")
        response = self._get_indicators(client, repo, params={"jerry": "hello"})
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"__all__": [{"message": "Got unexpected fields: jerry", "code": "unexpected"}]}
        }
        assert len(mock_metrics_store.get_requests()) == 0

    def test_get_raw_build_staff(self, staff_user_client, repo: Repo, user) -> None:
        run_id, _, raw_data, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(staff_user_client, repo, run_id, "raw")
        assert response.status_code == 200
        raw_data["run_info"]["timestamp"] = int(run_info.timestamp.timestamp())
        assert response.json() == raw_data
        DummyElasticRequests.assert_single_request()

    def test_get_raw_build_impersonation(self, settings, repo: Repo, user: ToolchainUser) -> None:
        admin = create_staff(username="bob", email="bob@jerrysplace.com", github_user_id="909090")
        client = self._get_client_for_user(user=user, settings=settings, impersonator=admin)
        run_id, _, raw_data, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(client, repo, run_id, "raw")
        assert response.status_code == 200
        raw_data["run_info"]["timestamp"] = int(run_info.timestamp.timestamp())
        assert response.json() == raw_data
        DummyElasticRequests.assert_single_request()

    def test_get_raw_build_invalid_repo(self, staff_user_client, repo: Repo, user) -> None:
        run_id, _, _, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(staff_user_client, repo="jerry", run_id=run_id, part="raw")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}
        DummyElasticRequests.assert_no_requests()

    def test_get_raw_build_invalid_repo_slug(self, staff_user_client, repo: Repo, user) -> None:
        run_id, _, _, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(staff_user_client, repo=repo.pk, run_id=run_id, part="raw")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}
        DummyElasticRequests.assert_no_requests()

    def test_get_raw_build_repo_not_associated_with_user(self, staff_user_client, staff_user: ToolchainUser) -> None:
        customer = Customer.create(slug="sidler", name="The Sidler")
        user = create_github_user(
            username="elaine", email="elaine@sidler.net", full_name="Elaine Benes", github_user_id="191133"
        )
        customer.add_user(user)
        repo = Repo.create(slug="talker", customer=customer, name="Long Talker")
        run_id, _, _, run_info = self._prepare_build(repo, user)

        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(staff_user_client, repo=repo, run_id=run_id, part="raw")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}
        DummyElasticRequests.assert_no_requests()

    def test_get_raw_build_doesnt_exist(self, staff_user_client, repo: Repo, user) -> None:
        run_id, _, _, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(staff_user_client, repo, run_id[:10], "raw")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}
        DummyElasticRequests.assert_single_request()

    def test_get_raw_build_denied(self, client, repo: Repo, user: ToolchainUser) -> None:
        run_id, _, _, run_info = self._prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(client, repo, run_id, "raw")
        assert response.status_code == 403
        assert response.json() == {"detail": "not allowed"}
        DummyElasticRequests.assert_no_requests()

    def test_get_build_trace_no_trace(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        (
            run_id,
            *_,
        ) = self._prepare_build(repo, user)
        response = self._get_build_extra(client, repo=repo, run_id=run_id, part="trace", extra={"user_api_id": "me"})
        assert response.status_code == 404

    def test_get_build_trace_non_existent_build(self, client: APIClient, repo: Repo) -> None:
        response = self._get_build_extra(client, repo, run_id="soup", part="trace", extra={"user_api_id": "me"})
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_build_trace(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        run_id, *_ = self._prepare_build(repo, user)
        store = RunInfoRawStore.for_repo(repo)

        store.save_build_json_file(
            run_id=run_id,
            json_bytes_or_file=load_bytes_fixture("zipkin_trace_1.json"),
            name="zipkin_trace",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            is_compressed=False,
        )
        response = self._get_build_extra(client, repo, run_id, part="trace", extra={"user_api_id": "me"})
        assert response.status_code == 200
        assert response.json() == load_fixture("zipkin_trace_1")

    def test_get_build_work_units(self, client, repo: Repo, user: ToolchainUser) -> None:
        run_info, key, raw_data = self._prepare_build_from_fixture(repo, user, "ci_build_pr_final_1")
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(client, repo, run_id=run_info.run_id, part="workunits")

        assert response.status_code == 200
        assert response.json() == raw_data["workunits"]
        DummyElasticRequests.assert_single_request()

    def test_get_build_work_units_invalid_bulld(self, client, repo: Repo) -> None:
        DummyElasticRequests.add_empty_search_response()
        response = self._get_build_extra(client, repo, run_id="pants_run_jerry", part="workunits")

        assert response.status_code == 404
        DummyElasticRequests.assert_single_request()

    def test_get_build_no_work_units(self, client, repo: Repo, user: ToolchainUser) -> None:
        raw_data = load_fixture("ci_build_pr_final_1")
        del raw_data["workunits"]
        run_info = self._store_build(
            repo, user, raw_data, datetime.datetime(2019, 4, 22, 19, 24, 44, tzinfo=datetime.timezone.utc)
        )
        DummyElasticRequests.add_search_response([run_info])
        response = self._get_build_extra(client, repo, run_id=run_info.run_id, part="workunits")

        assert response.status_code == 404
        assert response.json() == {"detail": "No Work Units associated with this build."}
        DummyElasticRequests.assert_single_request()


class TestSuggestValuesViewsApi(BaseTestViewsApi):
    def _get_suggested_values(self, client, repo, **kwargs) -> HttpResponse:
        extra = dict(QUERY_STRING=urlencode(kwargs, doseq=True)) if kwargs else {}
        url = f"{self._get_base_url(repo)}suggest/"
        return client.get(url, **extra)

    def _assert_suggest_request(self, request, repo, query):
        search_request = request.get_json_body()
        assert search_request == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": repo.customer_id}},
                        {"term": {"repo_id": repo.id}},
                    ]
                }
            },
            "size": 0,
            "_source": "title",
            "suggest": {
                "title_suggest": {"text": query, "completion": {"field": "title.completion", "skip_duplicates": True}}
            },
        }

    def test_get_title_values(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        DummyElasticRequests.add_suggest_response(
            suggest_name="title_suggest",
            values=["What do you need it for after you read it", "Moles — freckles’ ugly cousin"],
        )
        response = self._get_suggested_values(client, repo, q="mole")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {
            "values": ["What do you need it for after you read it", "Moles — freckles’ ugly cousin"]
        }
        request = DummyElasticRequests.get_request()
        self._assert_suggest_request(request, repo=repo, query="mole")

    def test_get_title_values_short(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        response = self._get_suggested_values(client, repo, q="le")
        assert response.status_code == 400
        assert response.json() == {
            "errors": [{"code": "invalid", "message": "Invalid query value, must be at least 3 characters"}]
        }
        DummyElasticRequests.assert_no_requests()

    def test_get_title_values_no_params(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        response = self._get_suggested_values(client, repo)
        assert response.status_code == 400
        assert response.json() == {"errors": [{"code": "missing", "message": "Missing 'q'"}]}
        DummyElasticRequests.assert_no_requests()

    def test_get_title_values_invalid_param(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        response = self._get_suggested_values(client, repo, query="mole")
        assert response.status_code == 400
        assert response.json() == {"errors": [{"code": "missing", "message": "Missing 'q'"}]}
        DummyElasticRequests.assert_no_requests()

    def test_get_title_values_extra_param(self, client: APIClient, repo: Repo, user: ToolchainUser) -> None:
        response = self._get_suggested_values(client, repo, q="mole", jerry="hello")
        assert response.status_code == 400
        assert response.json() == {"errors": [{"code": "invalid", "message": "Unused query parameters"}]}
        DummyElasticRequests.assert_no_requests()


class TestBuildArtifactsView(BaseTestViewsApi):
    def test_get_text_artifact(self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer) -> None:
        run_id = prepare_build_with_artifacts(repo, user, "david_puddy").run_id
        url = f"{self._get_base_url(repo, run_id)}artifacts/david_puddy.json/"
        response = client.get(url, {"user_api_id": "me"})
        assert response.status_code == 200
        assert response.content_type == "application/json"
        assert response.json() == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "content": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.2, pytest-6.0.1, py-1.9.0, pluggy-0.13.1\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionuOZCLl\nplugins: cov-2.8.1, icdiff-0.5, timeout-1.3.4, django-3.9.0\ncollected 18 items\n\nsrc/python/toolchain/buildsense/ingestion/run_processors/processor_test.py \x1b[32m.\x1b[0m\x1b[32m [  5%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                               [ 61%]\x1b[0m\nsrc/python/toolchain/buildsense/ingestion/run_processors/artifacts_test.py \x1b[32m.\x1b[0m\x1b[32m [ 66%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                        [ 72%]\x1b[0m\nsrc/python/toolchain/buildsense/ingestion/run_processors/junit_xml_test.py \x1b[32m.\x1b[0m\x1b[32m [ 77%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                       [ 88%]\x1b[0m\nsrc/python/toolchain/buildsense/ingestion/run_processors/zipkin_trace_test.py \x1b[32m.\x1b[0m\x1b[32m [ 94%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                        [100%]\x1b[0m\n\n\x1b[32m============================== \x1b[32m\x1b[1m18 passed\x1b[0m\x1b[32m in 0.97s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
            }
        ]

    def test_get_artifact_not_exists(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        run_id = prepare_build_with_artifacts(repo, user, "david_puddy.txt").run_id
        url = f"{self._get_base_url(repo, run_id)}artifacts/jerry.txt/"
        response = client.get(url, {"user_api_id": "me"})
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_get_artifact_build_dont_exists(
        self, client: APIClient, repo: Repo, user: ToolchainUser, customer: Customer
    ) -> None:
        run_id = prepare_build_with_artifacts(repo, user, "david_puddy.txt").run_id
        url = f"{self._get_base_url(repo, run_id)}artifacts/david_puddy.txt/"
        response = client.get(url, {"user_api_id": "me"})
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'
