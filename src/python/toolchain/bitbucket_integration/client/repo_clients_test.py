# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.bitbucket_integration.client.repo_clients import BitbucketRepoInfoClient
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture_payload

_BASE_URL = "http://scm-integration-api.tinsel.svc.cluster.local"


def add_bitbucket_pr_response_for_repo(httpx_mock, repo, pr_number: int, fixture: str | None = None):
    add_pr_response(
        httpx_mock=httpx_mock,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        pr_number=pr_number,
        fixture=fixture,
    )


def add_pr_response(httpx_mock, customer_id: str, repo_id: str, pr_number: int, fixture: str | None = None) -> None:
    url = f"{_BASE_URL}/api/v1/bitbucket/{customer_id}/{repo_id}/pull_requests/{pr_number}/"
    if fixture:
        pr_data = load_fixture_payload(fixture)["data"]["pullrequest"]
        httpx_mock.add_response(method="GET", url=url, json={"pull_request_data": pr_data})
    else:
        httpx_mock.add_response(method="GET", url=url, status_code=404)


def add_bitbucket_push_response_for_repo(
    httpx_mock, repo, ref_type: str, ref_name: str, commit_sha: str, fixture: str | None = None
):
    add_push_response(
        httpx_mock=httpx_mock,
        customer_id=repo.customer_id,
        repo_id=repo.id,
        ref_type=ref_type,
        ref_name=ref_name,
        commit_sha=commit_sha,
        fixture=fixture,
    )


def add_push_response(
    httpx_mock,
    customer_id: str,
    repo_id: str,
    ref_type: str,
    ref_name: str,
    commit_sha: str,
    fixture: str | None = None,
) -> None:
    url = f"{_BASE_URL}/api/v1/bitbucket/{customer_id}/{repo_id}/push/{ref_type}/{ref_name}/{commit_sha}/"
    if fixture:
        fixture_data = load_fixture_payload(fixture)["data"]
        change_data = fixture_data["push"]["changes"][0]
        httpx_mock.add_response(method="GET", url=url, json={"change": change_data, "actor": fixture_data["actor"]})
    else:
        httpx_mock.add_response(method="GET", url=url, status_code=404)


class TestBitbucketRepoInfoClient:
    @pytest.fixture()
    def client(self, settings) -> BitbucketRepoInfoClient:
        return BitbucketRepoInfoClient.for_repo(django_settings=settings, customer_id="ovaltine", repo_id="mandelbaum")

    def test_get_pull_request_info(self, httpx_mock, client: BitbucketRepoInfoClient) -> None:
        add_pr_response(httpx_mock, "ovaltine", "mandelbaum", 882, "pullrequest_updated")
        pr_data = client.get_pull_request_info(pr_number=882)
        assert pr_data is not None
        assert pr_data.number == 7
        assert pr_data.branch == "upgrades"
        assert pr_data.user_account_id == "6059303e630024006fab8c2b"
        assert pr_data.html_url == "https://bitbucket.org/festivus-miracle/minimal-pants/pull-requests/7"
        assert pr_data.title == "Add linters"
        assert httpx_mock.get_request() is not None

    def test_get_pull_request_info_no_info(self, httpx_mock, client: BitbucketRepoInfoClient) -> None:
        add_pr_response(httpx_mock, "ovaltine", "mandelbaum", 311)
        pr_data = client.get_pull_request_info(pr_number=311)
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
    def test_get_pull_request_info_invalid_pr(self, client: BitbucketRepoInfoClient, pr_num) -> None:
        with pytest.raises(ToolchainAssertion, match="Invalid pr_number="):
            client.get_pull_request_info(pr_number=pr_num)

    def test_get_push_info(self, httpx_mock, client: BitbucketRepoInfoClient) -> None:
        add_push_response(
            httpx_mock,
            customer_id="ovaltine",
            repo_id="mandelbaum",
            ref_type="branch",
            ref_name="jerry",
            commit_sha="moles",
            fixture="repo_push_pr_merge",
        )
        push_info = client.get_push_info(ref_type="branch", ref_name="jerry", commit_sha="moles")
        assert push_info is not None
        assert push_info.commit_sha == "d98f3c1d2ad48d6f7ed51281eb28ad3b233878c4"
        assert push_info.message == "Merged in upgrades (pull request #9)\n\nAdd & run linters"
        assert push_info.ref_type == "branch"
        assert push_info.ref_name == "main"
        assert push_info.user_account_id == "6059303e630024006fab8c2b"
        assert (
            push_info.html_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/commits/d98f3c1d2ad48d6f7ed51281eb28ad3b233878c4"
        )

    def test_get_push_info_missing(self, httpx_mock, client: BitbucketRepoInfoClient) -> None:
        add_push_response(
            httpx_mock,
            customer_id="ovaltine",
            repo_id="mandelbaum",
            ref_type="branch",
            ref_name="jerry",
            commit_sha="moles",
        )
        push_info = client.get_push_info(ref_type="branch", ref_name="jerry", commit_sha="moles")
        assert push_info is None
