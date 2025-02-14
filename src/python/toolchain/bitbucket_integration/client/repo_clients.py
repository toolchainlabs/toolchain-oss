# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.bitbucket_integration.client.common import get_http_client

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PullRequestInfo:
    number: int
    branch: str
    user_account_id: str
    html_url: str
    title: str

    @classmethod
    def from_response(cls, resp_json: dict) -> PullRequestInfo:
        return cls(
            number=resp_json["id"],
            branch=resp_json["source"]["branch"]["name"],
            user_account_id=resp_json["author"]["account_id"],
            html_url=resp_json["links"]["html"]["href"],
            title=resp_json["title"],
        )


@dataclass(frozen=True)
class PushInfo:
    commit_sha: str
    message: str
    user_account_id: str
    ref_type: str
    ref_name: str
    html_url: str

    @classmethod
    def from_response(cls, resp_json: dict) -> PushInfo:
        new_ref = resp_json["change"]["new"]
        target = new_ref["target"]
        return cls(
            commit_sha=target["hash"],
            user_account_id=resp_json["actor"]["account_id"],
            message=target["message"],
            ref_type=new_ref["type"],
            ref_name=new_ref["name"],
            html_url=target["links"]["html"]["href"],
        )


class BitbucketRepoInfoClient:
    @classmethod
    def for_repo(cls, *, django_settings, customer_id: str, repo_id: str) -> BitbucketRepoInfoClient:
        url_prefix = f"/api/v1/bitbucket/{customer_id}/{repo_id}/"
        client = get_http_client(django_settings, url_prefix=url_prefix)
        return cls(client=client)

    def __init__(self, *, client: httpx.Client) -> None:
        self._client = client

    def get_pull_request_info(self, *, pr_number: int) -> PullRequestInfo | None:
        if not pr_number:
            raise ToolchainAssertion(f"Invalid {pr_number=}")
        # See bitbucket_integration/api/urls.py
        response = self._client.get(f"pull_requests/{pr_number}/")
        if response.status_code == 404:
            # 404 is a legit response for this API
            return None
        # TODO: Error handling
        response.raise_for_status()
        pr_data = response.json()["pull_request_data"]
        return PullRequestInfo.from_response(pr_data)

    def get_push_info(self, *, ref_type: str, ref_name: str, commit_sha: str) -> PushInfo | None:
        # See bitbucket_integration/api/urls.py
        response = self._client.get(f"push/{ref_type}/{ref_name}/{commit_sha}/")
        if response.status_code == 404:
            # 404 is a legit response for this API
            return None
        # TODO: Error handling
        response.raise_for_status()
        return PushInfo.from_response(response.json())
