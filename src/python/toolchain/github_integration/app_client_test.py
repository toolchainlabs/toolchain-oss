# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging

import httpx
import pytest
from httpx import HTTPError
from jose import jwt

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer
from toolchain.github_integration.app_client import (
    AccessToken,
    GithubAppClient,
    GithubRepoClient,
    GithubServerError,
    MissingGithubPermissionsError,
    get_github_org_info,
    get_repo_client,
)
from toolchain.github_integration.constants import DataSource
from toolchain.github_integration.models import GithubRepo
from toolchain.github_integration.test_utils.fixtures_loader import load_fixture
from toolchain.util.test.util import assert_messages


def add_get_workflow_run_response(httpx_mock, fixture: str | dict | None, run_id: str, repo_fn: str) -> None:
    if not fixture:
        json_response = {
            "message": "Not Found",
            "documentation_url": "https://docs.github.com/rest/reference/actions#get-a-workflow-run",
        }
    elif isinstance(fixture, str):
        json_response = load_fixture(fixture)
    else:
        json_response = fixture

    httpx_mock.add_response(
        method="GET",
        url=f"https://api.github.com/repos/{repo_fn}/actions/runs/{run_id}",
        status_code=200 if fixture else 404,
        json=json_response,
    )


def add_install_token_response(httpx_mock, install_id: str) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"https://api.github.com/app/installations/{install_id}/access_tokens",
        json={
            "token": "gold-jerry-gold",
            "expires_at": "2020-06-03T22:14:10Z",
            "permissions": {"issues": "write", "contents": "read"},
            "repository_selection": "selected",
            "repositories": [],
        },
    )


def add_install_token_response_no_permissions(httpx_mock, install_id: str, http_status: int = 422) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"https://api.github.com/app/installations/{install_id}/access_tokens",
        status_code=http_status,
        json={
            "message": "The permissions requested are not granted to this installation.",
            "documentation_url": "https://docs.github.com/rest/reference/apps#create-an-installation-access-token-for-an-app",
        },
    )


class TestGithubAppClient:
    def _assert_request_auth(self, request) -> None:
        now = utcnow()
        marker, _, jwt_token = request.headers["Authorization"].partition(" ")
        assert marker == "Bearer"
        claims = jwt.get_unverified_claims(jwt_token)
        assert len(claims) == 3
        assert claims["iss"] == "bosco"
        assert claims["iat"] == pytest.approx(now.timestamp())
        assert claims["exp"] == pytest.approx((now + datetime.timedelta(minutes=7)).timestamp())

    def test_get_installation_access_token(self, httpx_mock, settings) -> None:
        add_install_token_response(httpx_mock, "39452")
        client = GithubAppClient.for_config(settings.GITHUB_CONFIG)
        token = client.get_installation_access_token(
            installation_id="39452", repo_ids=[744], permissions={"golden": "boy", "baby": "bluey"}
        )

        request = httpx_mock.get_request()
        assert request is not None
        self._assert_token_request(request, "39452")
        assert token.token == "gold-jerry-gold"
        assert token.expires_at == datetime.datetime(2020, 6, 3, 22, 14, 10, tzinfo=datetime.timezone.utc)
        assert token.permissions == {"issues": "write", "contents": "read"}

    @pytest.mark.parametrize("http_status", [422, 404])
    def test_get_installation_access_token_missing_permissions(self, httpx_mock, settings, http_status: int) -> None:
        add_install_token_response_no_permissions(httpx_mock, install_id="983749387", http_status=http_status)
        client = GithubAppClient.for_config(settings.GITHUB_CONFIG)
        with pytest.raises(MissingGithubPermissionsError, match="422 Unprocessable Entity|404 Not Found"):
            client.get_installation_access_token(
                installation_id="983749387", repo_ids=[744], permissions={"golden": "boy", "baby": "bluey"}
            )

        request = httpx_mock.get_request()
        assert request is not None
        self._assert_token_request(request, "983749387")

    @pytest.mark.parametrize("http_status", [501, 500, 503, 504])
    def test_get_installation_access_token_github_server_error(self, httpx_mock, settings, http_status: int) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/app/installations/983749387/access_tokens",
            status_code=http_status,
            content="I choose not to run.",
        )

        client = GithubAppClient.for_config(settings.GITHUB_CONFIG)
        with pytest.raises(GithubServerError, match="I choose not to run"):
            client.get_installation_access_token(
                installation_id="983749387", repo_ids=[744], permissions={"golden": "boy", "baby": "bluey"}
            )

        request = httpx_mock.get_request()
        assert request is not None
        self._assert_token_request(request, "983749387")

    @pytest.mark.parametrize("http_status", [401, 400, 403])
    def test_get_installation_access_token_github_client_error(self, httpx_mock, settings, http_status: int) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/app/installations/983749387/access_tokens",
            status_code=http_status,
            json={
                "message": "The permissions requested are not granted to this installation.",
                "documentation_url": "https://docs.github.com/rest/reference/apps#create-an-installation-access-token-for-an-app",
            },
        )

        client = GithubAppClient.for_config(settings.GITHUB_CONFIG)
        with pytest.raises(httpx.HTTPStatusError, match="Client error"):
            client.get_installation_access_token(
                installation_id="983749387", repo_ids=[744], permissions={"golden": "boy", "baby": "bluey"}
            )

        request = httpx_mock.get_request()
        assert request is not None
        self._assert_token_request(request, "983749387")

    def test_get_installation_access_token_network_error(self, httpx_mock, settings) -> None:
        httpx_mock.add_exception(
            httpx.ReadTimeout("No soup for you"),
            method="POST",
            url="https://api.github.com/app/installations/983749387/access_tokens",
        )

        client = GithubAppClient.for_config(settings.GITHUB_CONFIG)
        with pytest.raises(GithubServerError, match="Transport error getting token from GitHub: No soup for you"):
            client.get_installation_access_token(
                installation_id="983749387", repo_ids=[744], permissions={"golden": "boy", "baby": "bluey"}
            )

        request = httpx_mock.get_request()
        assert request is not None
        self._assert_token_request(request, "983749387")

    def _assert_token_request(self, request, install_id: str) -> None:
        assert request.method == "POST"
        assert request.url == f"https://api.github.com/app/installations/{install_id}/access_tokens"
        assert json.loads(request.read()) == {
            "repository_ids": [744],
            "permissions": {"golden": "boy", "baby": "bluey"},
        }
        assert request.headers["Accept"] == "application/vnd.github.machine-man-preview+json"
        self._assert_request_auth(request)

    def test_list_installations(self, httpx_mock, settings) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/app/installations",
            json=load_fixture("list_installations_response"),
        )
        client = GithubAppClient.for_config(settings.GITHUB_CONFIG)
        installations = client.list_installations()
        assert len(installations) == 1
        assert installations[0]["account"]["repos_url"] == "https://api.github.com/users/toolchainlabs/repos"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert request.url == "https://api.github.com/app/installations"
        self._assert_request_auth(request)


@pytest.mark.django_db()
class TestGithubRepoClient:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="ovaltine", name="Ovaltine!")

    @pytest.fixture()
    def github_repo(self, customer: Customer) -> GithubRepo:
        return GithubRepo.activate_or_create(
            repo_id="9844", install_id="4220", repo_name="gold", customer_id=customer.pk
        )

    @pytest.fixture()
    def repo_client(self, github_repo: GithubRepo) -> GithubRepoClient:
        token = AccessToken(token="movie-phone", expires_at=utcnow() + datetime.timedelta(minutes=3), permissions={})
        return GithubRepoClient(owner_slug="costanza", repo_slug="kenneth", access_token=token)

    def test_get_client(self, httpx_mock, settings, github_repo: GithubRepo) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/app/installations/4220/access_tokens",
            json={"token": "penske-material", "expires_at": "2020-06-03T22:14:10Z", "permissions": {}},
        )
        client = get_repo_client(github_repo)
        assert httpx_mock.get_request() is not None
        assert client._owner == "ovaltine"
        assert client._repo == "gold"
        assert client.get_token() == "penske-material"

    def test_github_api_responses(self, httpx_mock, repo_client: GithubRepoClient) -> None:
        responses_and_fixtures = [
            ("https://api.github.com/repos/costanza/kenneth", "github_api_repo"),
            ("https://api.github.com/repos/costanza/kenneth/traffic/views", "github_api_views"),
            ("https://api.github.com/repos/costanza/kenneth/traffic/clones", "github_api_clones"),
            ("https://api.github.com/repos/costanza/kenneth/traffic/popular/paths", "github_api_paths"),
            ("https://api.github.com/repos/costanza/kenneth/traffic/popular/referrers", "github_api_referrers"),
        ]
        for response_url, json_fixture in responses_and_fixtures:
            httpx_mock.add_response(method="GET", url=response_url, json=load_fixture(json_fixture))
        assert repo_client.get_repo_info() == load_fixture("github_api_repo")
        assert httpx_mock.get_requests()[-1].url == "https://api.github.com/repos/costanza/kenneth"

        assert repo_client.get_repo_views() == load_fixture("github_api_views")
        assert httpx_mock.get_requests()[-1].url == "https://api.github.com/repos/costanza/kenneth/traffic/views"

        assert repo_client.get_clones() == load_fixture("github_api_clones")
        assert httpx_mock.get_requests()[-1].url == "https://api.github.com/repos/costanza/kenneth/traffic/clones"

        assert repo_client.get_popular_referral_paths() == load_fixture("github_api_paths")
        assert (
            httpx_mock.get_requests()[-1].url == "https://api.github.com/repos/costanza/kenneth/traffic/popular/paths"
        )

        assert repo_client.get_popular_referral_sources() == load_fixture("github_api_referrers")
        assert (
            httpx_mock.get_requests()[-1].url
            == "https://api.github.com/repos/costanza/kenneth/traffic/popular/referrers"
        )

    def _assert_info_and_debug_only(self, caplog):
        assert {rec.levelno for rec in caplog.records if rec.levelno > logging.INFO} == set()

    def test_list_webhooks(self, httpx_mock, repo_client: GithubRepoClient, caplog) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/repos/costanza/kenneth/hooks",
            json=load_fixture("list_webhooks_response"),
        )
        hooks = repo_client.list_webhooks()
        assert len(hooks) == 1
        hook = hooks[0]
        assert hook.webhook_id == "12182943"
        self._assert_info_and_debug_only(caplog)

    def test_list_webhooks_http_error(self, httpx_mock, repo_client: GithubRepoClient, caplog) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/repos/costanza/kenneth/hooks",
            status_code=403,
            headers={"X-GitHub-Request-Id": "no-soup-for-you"},
            json={"message": "come back one year"},
        )
        with pytest.raises(HTTPError, match="Client error '403 Forbidden' for url"):
            repo_client.list_webhooks()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer movie-phone"
        assert_messages(caplog, "github_request_failed")

    def test_create_webhook(self, httpx_mock, repo_client: GithubRepoClient, caplog) -> None:
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/repos/costanza/kenneth/hooks",
            json=load_fixture("create_webhook_response"),
        )
        hook = repo_client.create_webhook(
            url="https://bosco.com/newman/", secret="strongbox", events=("superman", "movie")
        )
        assert hook.webhook_id == "225568244"
        assert hook.events == ("pull_request", "push")
        assert hook.url == "https://staging.webhooks.toolchain.com/github/repo/"
        assert hook.active is True
        assert hook.hook_type == "Repository"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer movie-phone"
        assert json.loads(request.read()) == {
            "active": True,
            "config": {
                "content_type": "json",
                "insecure_ssl": 0,
                "secret": "strongbox",
                "url": "https://bosco.com/newman/",
            },
            "events": ["superman", "movie"],
            "name": "web",
        }
        self._assert_info_and_debug_only(caplog)

    def test_create_webhook_invalid_secret(self, repo_client: GithubRepoClient) -> None:
        with pytest.raises(ToolchainAssertion, match="Invalid webhook secret"):
            repo_client.create_webhook(url="https://bosco.com/newman/", secret="", events=("superman", "movie"))

    def test_delete_webhook(self, httpx_mock, repo_client: GithubRepoClient, caplog) -> None:
        httpx_mock.add_response(method="DELETE", url="https://api.github.com/repos/costanza/kenneth/hooks/837731")
        repo_client.delete_webhook("837731")
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer movie-phone"
        assert request.url == "https://api.github.com/repos/costanza/kenneth/hooks/837731"
        self._assert_info_and_debug_only(caplog)

    def test_delete_webhook_invalid_webhook_id(self, repo_client: GithubRepoClient) -> None:
        with pytest.raises(ToolchainAssertion, match="webhook_id can't be empty"):
            repo_client.delete_webhook("")

    def test_update_webhook(self, httpx_mock, repo_client: GithubRepoClient) -> None:
        httpx_mock.add_response(
            method="PATCH",
            url="https://api.github.com/repos/costanza/kenneth/hooks/43311",
            json=load_fixture("create_webhook_response"),
        )
        hook = repo_client.update_webhook(
            webhook_id="43311", url="https://bosco.com/newman/", secret="strongbox", events=("superman", "movie")
        )
        assert hook.webhook_id == "225568244"
        assert hook.events == ("pull_request", "push")
        assert hook.url == "https://staging.webhooks.toolchain.com/github/repo/"
        assert hook.active is True
        assert hook.hook_type == "Repository"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer movie-phone"
        assert json.loads(request.read()) == {
            "active": True,
            "config": {
                "content_type": "json",
                "insecure_ssl": 0,
                "secret": "strongbox",
                "url": "https://bosco.com/newman/",
            },
            "events": ["superman", "movie"],
        }

    def test_get_workflow_actions_run(self, httpx_mock, repo_client: GithubRepoClient) -> None:
        add_get_workflow_run_response(
            httpx_mock, fixture="get_workflow_run_response", run_id="77772222", repo_fn="costanza/kenneth"
        )
        workflow_run, json_data = repo_client.get_workflow_actions_run("77772222")
        assert httpx_mock.get_request() is not None
        assert workflow_run is not None
        assert json_data is not None
        assert isinstance(json_data, dict)
        assert len(json_data) == 27
        assert json_data == load_fixture("get_workflow_run_response")
        assert workflow_run.run_id == "621923665"
        assert workflow_run.event == "pull_request"
        assert workflow_run.status == "completed"
        assert workflow_run.repo_id == "51405305"
        assert workflow_run.head_sha == "3f535d72bb3c0495393988f04bf3d6c2f5474716"
        assert workflow_run.created_at == datetime.datetime(2021, 3, 4, 18, 1, 2, tzinfo=datetime.timezone.utc)
        assert workflow_run.updated_at == datetime.datetime(2021, 3, 4, 18, 5, 55, tzinfo=datetime.timezone.utc)
        assert workflow_run.check_suite_id == "2180491069"
        assert workflow_run.url == "https://github.com/toolchainlabs/toolchain/actions/runs/621923665"
        assert workflow_run.source == DataSource.API
        assert utcnow().timestamp() == pytest.approx(workflow_run.last_fetch_time.timestamp())
        assert workflow_run.is_completed is True
        assert workflow_run.is_pull_request is True
        assert workflow_run.is_running_or_queued is False

    def test_get_workflow_actions_run_not_found(self, httpx_mock, repo_client: GithubRepoClient) -> None:
        add_get_workflow_run_response(httpx_mock, fixture=None, run_id="9933333", repo_fn="costanza/kenneth")

        workflow_run, json_data = repo_client.get_workflow_actions_run("9933333")
        assert workflow_run is None
        assert json_data is None
        assert httpx_mock.get_request() is not None

    @pytest.mark.parametrize("http_status", [501, 500, 503, 504])
    def test_get_workflow_actions_run_github_server_error(
        self, httpx_mock, repo_client: GithubRepoClient, http_status: int
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/repos/costanza/kenneth/actions/runs/7771818",
            status_code=http_status,
            content="I choose not to run.",
        )
        with pytest.raises(GithubServerError, match="I choose not to run"):
            repo_client.get_workflow_actions_run("7771818")
        assert httpx_mock.get_request() is not None

    def test_get_workflow_actions_run_read_timeout(self, httpx_mock, repo_client: GithubRepoClient) -> None:
        httpx_mock.add_exception(
            httpx.ReadTimeout("No soup for you"),
            method="GET",
            url="https://api.github.com/repos/costanza/kenneth/actions/runs/9933333",
        )

        workflow_run, json_data = repo_client.get_workflow_actions_run("9933333")
        assert workflow_run is None
        assert json_data is None
        assert httpx_mock.get_request() is not None

    def test_list_issues(self, httpx_mock, repo_client: GithubRepoClient) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.github.com/repos/costanza/kenneth/issues?state=all&sort=created&order=desc&per_page=100&page=39",
            status_code=200,
            json=load_fixture("list_repo_issues"),
        )
        issues_list = repo_client.list_issues(page=39)
        assert len(issues_list) == 2
        assert issues_list[1]["title"] == "Improve naming of Python `Lockfile` types"
        request = httpx_mock.get_request()
        assert (
            request.url
            == "https://api.github.com/repos/costanza/kenneth/issues?state=all&sort=created&order=desc&per_page=100&page=39"
        )


def test_get_github_org_info(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.github.com/users/google",
        status_code=200,
        json=load_fixture("github_api_org_url_1"),
    )
    org_info = get_github_org_info("google")
    assert org_info.slug == "google"
    assert org_info.name == "Google"


def test_get_github_org_info_http_error(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET", url="https://api.github.com/users/jerry", status_code=503, text="he took it out"
    )
    org_info = get_github_org_info("jerry")
    assert org_info.slug == "jerry"
    assert org_info.name == "jerry"


def test_get_github_org_info_network_error(httpx_mock) -> None:
    httpx_mock.add_exception(
        httpx.ReadTimeout("no soup for you"), method="GET", url="https://api.github.com/users/kramer"
    )
    org_info = get_github_org_info("kramer")
    assert org_info.slug == "kramer"
    assert org_info.name == "kramer"
