# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import uuid

import httpx
import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.github_integration.client.repo_clients import (
    GithubCustomerReposClient,
    GithubRepoInfoClient,
    RepoWebhookClient,
)
from toolchain.github_integration.common.constants import RepoState
from toolchain.github_integration.common.records import GitHubEvent
from toolchain.github_integration.test_utils.fixtures_loader import load_fixture, load_fixture_payload

_DEFAULT_BASE_URL = "http://scm-integration-api.tinsel.svc.cluster.local:80"


def load_as_github_event(fixture_name: str, event_id: str | None = None) -> dict:
    fixture = load_fixture(fixture_name)
    return {
        "event_type": fixture["headers"]["X-GitHub-Event"],
        "event_id": event_id or str(uuid.uuid4()),
        "new_signature": "festivus",
        "json_payload": fixture["payload"],
    }


def add_get_install_info_response(
    httpx_mock, customer_id: str, with_configure_link: bool = False, base_url: str | None = None
):
    data = {"install_link": "https://github.com/apps/toolchain-dev/installations/new"}
    if with_configure_link:
        data.update(
            {
                "install_id": "10322049",
                "configure_link": "https://github.com/organizations/toolchainlabs/settings/installations/10322049",
            }
        )
    url = f"{base_url or _DEFAULT_BASE_URL}/api/v1/github/{customer_id}/"
    httpx_mock.add_response(method="OPTIONS", url=url, json={"data": data})


def add_github_pr_response_for_repo(httpx_mock, repo, pr_number: int, fixture: str | None = None):
    add_pr_response(
        httpx_mock,
        _DEFAULT_BASE_URL,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        pr_number=pr_number,
        fixture=fixture,
    )


def add_pr_response_exception_for_repo(
    httpx_mock, repo, pr_number: int, exception_cls: type[httpx.RequestError]
) -> None:
    add_pr_response_exception(httpx_mock, _DEFAULT_BASE_URL, repo.customer_id, repo.id, pr_number, exception_cls)


def add_pr_response(
    httpx_mock, base_url: str, customer_id: str, repo_id: str, pr_number: int, fixture: str | None = None
) -> None:
    url = f"{base_url}/api/v1/github/{customer_id}/{repo_id}/pull_requests/{pr_number}/"
    if fixture:
        pr_data = load_fixture_payload(fixture)["pull_request"]
        httpx_mock.add_response(method="GET", url=url, json={"pull_request_data": pr_data})
    else:
        httpx_mock.add_response(method="GET", url=url, status_code=404)


def add_pr_response_exception(
    httpx_mock,
    base_url: str,
    customer_id: str,
    repo_id: str,
    pr_number: int,
    exception_cls: type[httpx.RequestError],
) -> None:
    url = f"{base_url}/api/v1/github/{customer_id}/{repo_id}/pull_requests/{pr_number}/"
    httpx_mock.add_exception(exception_cls("no soup for you"), method="GET", url=url)


def add_commit_response_for_repo(httpx_mock, repo, branch: str, commit_sha: str, fixture: str | None = None):
    add_commit_response(
        httpx_mock,
        _DEFAULT_BASE_URL,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        branch=branch,
        commit_sha=commit_sha,
        fixture=fixture,
    )


def add_commit_response(
    httpx_mock, base_url, customer_id, repo_id, branch: str, commit_sha: str, fixture: str | None = None
) -> None:
    url = f"{base_url}/api/v1/github/{customer_id}/{repo_id}/commit/{branch}/{commit_sha}/"
    if fixture:
        commit_data = load_fixture_payload(fixture)["head_commit"]
        httpx_mock.add_response(method="GET", url=url, json={"commit_data": commit_data})
    else:
        httpx_mock.add_response(method="GET", url=url, status_code=404)


def add_github_push_response_for_repo(responses, repo, branch: str, commit_sha: str, fixture: str | None = None):
    add_push_response(
        responses,
        _DEFAULT_BASE_URL,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        branch=branch,
        commit_sha=commit_sha,
        fixture=fixture,
    )


def add_push_response(
    httpx_mock, base_url, customer_id, repo_id, branch: str, commit_sha: str, fixture: str | None = None
) -> None:
    url = f"{base_url}/api/v1/github/{customer_id}/{repo_id}/push/{branch}/{commit_sha}/"
    if fixture:
        push_data = load_fixture_payload(fixture)
        del push_data["organization"]
        del push_data["repository"]
        httpx_mock.add_response(method="GET", url=url, json={"push_data": push_data})
    else:
        httpx_mock.add_response(method="GET", url=url, status_code=404)


def add_ci_resolve_error_response_for_repo(httpx_mock, repo, status: int, error: str) -> None:
    add_ci_resolve_error_response(
        httpx_mock,
        _DEFAULT_BASE_URL,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        status_code=status,
        error=error,
    )


def add_ci_resolve_response_for_repo(httpx_mock, repo, user_id: str, *labels: str) -> None:
    add_ci_resolve_response(
        httpx_mock,
        _DEFAULT_BASE_URL,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        user_id=user_id,
        labels=labels,
    )


def add_ci_resolve_response(
    httpx_mock, base_url: str, customer_id: str, repo_id: str, user_id: str, labels: tuple[str, ...]
) -> None:
    url = f"{base_url}/api/v1/github/{customer_id}/{repo_id}/ci/"
    httpx_mock.add_response(
        method="POST",
        url=url,
        json={
            "key": "trc_18_201412766_439751780",
            "user_id": user_id,
            "labels": list(labels),
            "ci_link": "https://jerry.com/festivus",
            "pr_number": "8882",
        },
    )


def add_ci_resolve_error_response(
    httpx_mock, base_url: str, customer_id: str, repo_id: str, status_code: int, error: str
) -> None:
    url = f"{base_url}/api/v1/github/{customer_id}/{repo_id}/ci/"
    httpx_mock.add_response(method="POST", url=url, status_code=status_code, json={"error": error})


class TestGithubRepoInfoClient:
    @pytest.fixture()
    def client(self, settings) -> GithubRepoInfoClient:
        return GithubRepoInfoClient.for_repo(settings, customer_id="ovaltine", repo_id="mandelbaum")

    def test_get_pull_request_info(self, httpx_mock, client) -> None:
        add_pr_response(httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", 5769, "pull_request_opened")
        pr_data = client.get_pull_request_info(pr_number=5769)
        assert pr_data is not None
        assert pr_data.number == 5769
        assert pr_data.branch == "helen"
        assert pr_data.username == "asherf"
        assert pr_data.user_id == "1268088"
        assert pr_data.html_url == "https://github.com/toolchainlabs/toolchain/pull/5769"
        assert pr_data.title == "Parse webhooks responses."
        assert httpx_mock.get_request() is not None

    def test_get_pull_request_info_no_info(self, httpx_mock, client) -> None:
        add_pr_response(httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", 2213)
        pr_data = client.get_pull_request_info(pr_number=2213)
        assert pr_data is None
        assert httpx_mock.get_request() is not None

    @pytest.mark.parametrize(
        "pr_num",
        [
            None,
            0,
            "",
        ],
    )
    def test_get_pull_request_info_invalid_pr(self, client, pr_num) -> None:
        with pytest.raises(ToolchainAssertion, match="Invalid pr_number="):
            client.get_pull_request_info(pr_number=pr_num)

    def test_get_commit_info(self, httpx_mock, client) -> None:
        add_commit_response(
            httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", "puddy", "8877abeebc", "repo_push_nested_branch"
        )
        commit_info = client.get_commit_info(ref_name="puddy", commit_sha="8877abeebc")
        assert commit_info is not None
        assert commit_info.commit_sha == "fb667312699fbcd018649073e0acecdfd10b37ef"
        assert commit_info.message == "Use xfail instead of skip. (#6547)"
        assert commit_info.username == "asherf"
        assert (
            commit_info.html_url
            == "https://github.com/toolchainlabs/toolchain/commit/fb667312699fbcd018649073e0acecdfd10b37ef"
        )

        assert httpx_mock.get_request() is not None

    def test_get_pull_request_info_read_timeout(self, httpx_mock, client) -> None:
        add_pr_response_exception(
            httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", 2213, exception_cls=httpx.ReadTimeout
        )
        with pytest.raises(httpx.ReadTimeout, match="no soup for you"):
            client.get_pull_request_info(pr_number=2213)

    def test_get_pull_request_info_read_timeout_silence(self, settings, httpx_mock) -> None:
        add_pr_response_exception(
            httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", 2213, exception_cls=httpx.ReadTimeout
        )
        client = GithubRepoInfoClient.for_repo(
            settings, customer_id="ovaltine", repo_id="mandelbaum", silence_timeouts=True
        )
        assert client.get_pull_request_info(pr_number=2213) is None

    @pytest.mark.parametrize(
        "exception_cls",
        [httpx.ConnectError, httpx.ConnectTimeout, httpx.CloseError],
    )
    def test_get_pull_request_info_with_silence_dont_silence_other_network_errors(
        self, settings, httpx_mock, exception_cls: type[httpx.RequestError]
    ) -> None:
        add_pr_response_exception(
            httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", 2213, exception_cls=exception_cls
        )
        client = GithubRepoInfoClient.for_repo(
            settings, customer_id="ovaltine", repo_id="mandelbaum", silence_timeouts=True
        )
        with pytest.raises(exception_cls, match="no soup for you"):
            client.get_pull_request_info(pr_number=2213)

    @pytest.mark.parametrize(
        ("branch", "commit"),
        [(None, None), (None, ""), ("", ""), ("puffy", ""), ("", "shirt")],
    )
    def test_get_commit_info_invalid_params(self, client, branch, commit) -> None:
        with pytest.raises(ToolchainAssertion, match="Invalid ref_name="):
            client.get_commit_info(ref_name=branch, commit_sha=commit)

    def test_get_commit_info_no_info(self, httpx_mock, client) -> None:
        add_commit_response(httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", "puddy", "8877abee003")
        commit_info = client.get_commit_info(ref_name="puddy", commit_sha="8877abee003")
        assert commit_info is None
        assert httpx_mock.get_request() is not None

    def test_get_push_info(self, httpx_mock, client) -> None:
        add_push_response(
            httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", "puddy", "8877abeebc", "repo_push_nested_branch"
        )

        push_info = client.get_push_info(ref_name="puddy", commit_sha="8877abeebc")
        assert push_info is not None
        assert push_info.commit_sha == "fb667312699fbcd018649073e0acecdfd10b37ef"
        assert push_info.message == "Use xfail instead of skip. (#6547)"
        assert (
            push_info.html_url
            == "https://github.com/toolchainlabs/toolchain/commit/fb667312699fbcd018649073e0acecdfd10b37ef"
        )
        assert push_info.sender_username == "asherf"
        assert push_info.sender_user_id == "1268088"

        assert httpx_mock.get_request() is not None

    @pytest.mark.parametrize(
        ("branch", "commit"),
        [(None, None), (None, ""), ("", ""), ("puffy", ""), ("", "shirt")],
    )
    def test_get_push_info_invalid_params(self, client, branch, commit) -> None:
        with pytest.raises(ToolchainAssertion, match="Invalid ref_name="):
            client.get_push_info(ref_name=branch, commit_sha=commit)

    def test_get_push_info_no_info(self, httpx_mock, client) -> None:
        add_push_response(httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", "puddy", "8877abee003")
        push_info = client.get_push_info(ref_name="puddy", commit_sha="8877abee003")
        assert push_info is None
        assert httpx_mock.get_request() is not None

    def test_resolve_ci_build(self, httpx_mock, client) -> None:
        add_ci_resolve_response(
            httpx_mock, _DEFAULT_BASE_URL, "ovaltine", "mandelbaum", user_id="newman", labels=("uncle", "leo")
        )
        ci_build = client.resolve_ci_build(
            ci_env_vars={"TRAVIS": "true", "KRAMER": "LEVELS"}, started_treshold=datetime.timedelta(seconds=96.67267)
        )
        assert ci_build is not None
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.read()) == {
            "ci_env": {"TRAVIS": "true", "KRAMER": "LEVELS"},
            "started_treshold_sec": 96,
        }

    def test_resolve_ci_build_denied(self, httpx_mock, client) -> None:
        url = f"{_DEFAULT_BASE_URL}/api/v1/github/ovaltine/mandelbaum/ci/"
        httpx_mock.add_response(method="POST", url=url, status_code=403, json={"error": "You are an Anti-Dentite"})
        ci_build = client.resolve_ci_build(
            ci_env_vars={"TRAVIS": "true", "KRAMER": "LEVELS"}, started_treshold=datetime.timedelta(seconds=206.27267)
        )
        assert ci_build is None
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.read()) == {
            "ci_env": {"TRAVIS": "true", "KRAMER": "LEVELS"},
            "started_treshold_sec": 206,
        }


class TestRepoWebhookClient:
    @pytest.fixture()
    def client(self, settings) -> RepoWebhookClient:
        return RepoWebhookClient.for_settings(settings)

    def test_get_webhook_secret(self, httpx_mock, client: RepoWebhookClient) -> None:
        httpx_mock.add_response(
            method="GET",
            url="http://scm-integration-api.tinsel.svc.cluster.local/api/v1/github/hooks/repos/772661/",
            json={"repo": {"name": "jerry", "secret": "European carry-all"}},
        )
        webhook_secret = client.get_webhook_secret(github_repo_id=772661)
        assert webhook_secret == "European carry-all"

    def test_post_github_webhook(self, httpx_mock, client: RepoWebhookClient) -> None:
        httpx_mock.add_response(
            method="POST",
            url="http://scm-integration-api.tinsel.svc.cluster.local:80/api/v1/github/hooks/repos/80024/",
            json={"handled": False},
        )
        event_dict = load_as_github_event("pull_request_synchronize", event_id="wallet")
        handled = client.post_github_webhook(github_repo_id=80024, event=GitHubEvent.from_json(event_dict))
        assert handled is False
        request = httpx_mock.get_request()
        assert request is not None
        request_json = json.loads(request.read())
        payload = request_json.pop("json_payload")
        assert request_json == {
            "event_type": "pull_request",
            "event_id": "wallet",
            "signature": "festivus",
            "new_signature": "festivus",
        }
        assert len(payload) == 8
        assert payload["number"] == 5769
        assert payload["pull_request"]["user"]["site_admin"] is False


class TestGithubCustomerReposClient:
    @pytest.fixture()
    def client(self, settings) -> GithubCustomerReposClient:
        return GithubCustomerReposClient.for_customer(settings, customer_id="festivus")

    def test_get_repos_empty(self, httpx_mock, client: GithubCustomerReposClient) -> None:
        httpx_mock.add_response(
            method="GET",
            url="http://scm-integration-api.tinsel.svc.cluster.local:80/api/v1/github/festivus/",
            json={"results": []},
        )
        assert client.get_repos() == tuple()
        assert httpx_mock.get_request() is not None

    def test_get_repos(self, httpx_mock, client: GithubCustomerReposClient) -> None:
        httpx_mock.add_response(
            method="GET",
            url="http://scm-integration-api.tinsel.svc.cluster.local:80/api/v1/github/festivus/",
            json={
                "results": [
                    {
                        "created_at": "2020-10-06T20:44:58+00:00",
                        "name": "tinsel",
                        "state": "inactive",
                        "repo_id": "77221",
                    },
                    {"created_at": "2020-11-06T02:18:11+00:00", "name": "pole", "state": "active", "repo_id": "99922"},
                ]
            },
        )
        repos = client.get_repos()
        assert httpx_mock.get_request() is not None
        assert len(repos) == 2
        assert repos[0].repo_id == "77221"
        assert repos[0].state == RepoState.INACTIVE
        assert repos[0].name == "tinsel"
        assert repos[0].created_at == datetime.datetime(2020, 10, 6, 20, 44, 58, tzinfo=datetime.timezone.utc)

        assert repos[1].repo_id == "99922"
        assert repos[1].state == RepoState.ACTIVE
        assert repos[1].name == "pole"
        assert repos[1].created_at == datetime.datetime(2020, 11, 6, 2, 18, 11, tzinfo=datetime.timezone.utc)

    def test_get_install_info_no_installs(self, httpx_mock, client: GithubCustomerReposClient) -> None:
        add_get_install_info_response(
            httpx_mock, "festivus", base_url="http://scm-integration-api.tinsel.svc.cluster.local:80"
        )
        install_info = client.get_install_info()
        assert httpx_mock.get_request() is not None
        assert install_info.install_link == "https://github.com/apps/toolchain-dev/installations/new"
        assert install_info.configure_link is None

    def test_get_install_info(self, httpx_mock, client: GithubCustomerReposClient) -> None:
        add_get_install_info_response(
            httpx_mock,
            "festivus",
            with_configure_link=True,
            base_url="http://scm-integration-api.tinsel.svc.cluster.local:80",
        )
        install_info = client.get_install_info()
        assert httpx_mock.get_request() is not None
        assert install_info.install_link == "https://github.com/apps/toolchain-dev/installations/new"
        assert (
            install_info.configure_link
            == "https://github.com/organizations/toolchainlabs/settings/installations/10322049"
        )
