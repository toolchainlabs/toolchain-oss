# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

import httpx
from dateutil.parser import parse

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.github_integration.client.common import get_http_client
from toolchain.github_integration.common.constants import RepoState
from toolchain.github_integration.common.records import GitHubEvent, PullRequestInfo

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GithubRepoInfo:
    repo_id: str
    state: RepoState
    name: str
    created_at: datetime.datetime

    @classmethod
    def from_response(cls, resp_json: dict) -> GithubRepoInfo:
        return cls(
            repo_id=resp_json["repo_id"],
            name=resp_json["name"],
            state=RepoState(resp_json["state"]),
            created_at=parse(resp_json["created_at"]),
        )


@dataclass(frozen=True)
class InstallInfo:
    install_link: str
    configure_link: str | None

    @classmethod
    def from_response(cls, resp_json: dict) -> InstallInfo:
        return cls(install_link=resp_json["install_link"], configure_link=resp_json.get("configure_link"))


@dataclass(frozen=True)
class CIBuildDetails:
    key: str
    user_id: str
    labels: tuple[str, ...]

    @classmethod
    def from_response(cls, resp_json: dict) -> CIBuildDetails:
        return cls(key=resp_json["key"], user_id=resp_json["user_id"], labels=tuple(resp_json["labels"]))


@dataclass(frozen=True)
class CommitInfo:
    commit_sha: str
    message: str
    username: str
    html_url: str

    @classmethod
    def from_response(cls, resp_json: dict) -> CommitInfo:
        author = resp_json["author"]
        return cls(
            commit_sha=resp_json["id"],
            message=resp_json["message"],
            username=author["username"],
            html_url=resp_json["url"],
        )


@dataclass(frozen=True)
class PushInfo:
    commit_sha: str
    message: str
    html_url: str
    sender_username: str
    sender_user_id: str

    @classmethod
    def from_response(cls, resp_json: dict) -> PushInfo:
        sender = resp_json["sender"]
        head_commit = resp_json["head_commit"]
        return cls(
            commit_sha=head_commit["id"],
            message=head_commit["message"],
            html_url=head_commit["url"],
            sender_username=sender["login"],
            sender_user_id=str(sender["id"]),
        )


class GithubRepoInfoClient:
    @classmethod
    def for_repo(
        cls, django_settings, *, customer_id: str, repo_id: str, silence_timeouts: bool = False
    ) -> GithubRepoInfoClient:
        url_prefix = f"/api/v1/github/{customer_id}/{repo_id}/"
        client = get_http_client(django_settings, url_prefix=url_prefix)
        return cls(client=client, silence_timeouts=silence_timeouts)

    def __init__(self, *, client: httpx.Client, silence_timeouts: bool) -> None:
        self._client = client
        self._silence_timeouts = silence_timeouts

    def _do_get_request(self, path: str, ignored_status_codes: tuple[int, ...] = tuple()) -> dict | None:
        try:
            response = self._client.get(path)
        except httpx.ReadTimeout as error:
            _logger.warning(f"Read timeout {error!r} from {error.request.url}")
            if self._silence_timeouts:
                return None
            raise
        if response.status_code in ignored_status_codes:
            return None
        # TODO: Error handling
        response.raise_for_status()
        return response.json()

    def get_pull_request_info(self, *, pr_number: int) -> PullRequestInfo | None:
        if not pr_number:
            raise ToolchainAssertion(f"Invalid {pr_number=}")
        # See github_integration/api/urls.py, 404 is a legit response for this API
        response = self._do_get_request(f"pull_requests/{pr_number}/", ignored_status_codes=(404,))
        return PullRequestInfo.from_pr_data(response["pull_request_data"]) if response else None

    def get_commit_info(self, *, ref_name: str, commit_sha: str) -> CommitInfo | None:
        # See github_integration/api/urls.py
        if not ref_name or not commit_sha:
            raise ToolchainAssertion(f"Invalid {ref_name=} or {commit_sha=}")
        # 404 is a legit response for this API
        response = self._do_get_request(f"commit/{ref_name}/{commit_sha}/", ignored_status_codes=(404,))
        return CommitInfo.from_response(response["commit_data"]) if response else None

    def get_push_info(self, *, ref_name: str, commit_sha: str) -> PushInfo | None:
        # See github_integration/api/urls.py
        if not ref_name or not commit_sha:
            raise ToolchainAssertion(f"Invalid {ref_name=} or {commit_sha=}")
        # 404 is a legit response for this API
        response = self._do_get_request(f"push/{ref_name}/{commit_sha}/", ignored_status_codes=(404,))
        return PushInfo.from_response(response["push_data"]) if response else None

    def resolve_ci_build(self, ci_env_vars: dict, started_treshold: datetime.timedelta) -> CIBuildDetails | None:
        # See github_integration/api/urls.py
        payload = {"ci_env": ci_env_vars, "started_treshold_sec": int(started_treshold.total_seconds())}
        response = self._client.post("ci/", json=payload)
        if response.headers.get("Content-Type") != "application/json":
            _logger.warning(f"Got a non-json response: status_code={response.status_code} text={response.text[:500]}")
            return None
        resp_json = response.json()
        if response.status_code != 200:
            error = resp_json.get("error") or "NA"
            _logger.warning(f"resolve_ci_build failed: {error=} status_code={response.status_code}")
            return None
        return CIBuildDetails.from_response(resp_json)


class RepoWebhookClient:
    @classmethod
    def for_settings(cls, django_settings) -> RepoWebhookClient:
        # We allow for longer timeout here, since the API in the github-integration views (under scm-integration-api service)
        # Write to s3 and from time to time this can have higher latency.
        # See: github_integration/api/views.py:handle_github_repo_event
        client = get_http_client(django_settings, url_prefix="api/v1/", timeout=10)
        return cls(client=client)

    def __init__(self, *, client: httpx.Client) -> None:
        self._client = client

    def get_webhook_secret(self, *, github_repo_id: int) -> str | None:
        # See github_integration/api/urls.py
        response = self._client.get(f"github/hooks/repos/{github_repo_id}/")
        if response.status_code == 404:
            # 404 is a legit response for this API
            return None
        # TODO: Error handling
        response.raise_for_status()
        return response.json()["repo"]["secret"]

    def post_github_webhook(self, *, github_repo_id: int, event: GitHubEvent) -> bool:
        # See github_integration/api/urls.py
        event_json = event.to_json_dict()
        response = self._client.post(f"github/hooks/repos/{github_repo_id}/", json=event_json)
        response.raise_for_status()
        return response.json()["handled"]


class GithubCustomerReposClient:
    @classmethod
    def for_customer(cls, django_settings, *, customer_id: str) -> GithubCustomerReposClient:
        client = get_http_client(django_settings, url_prefix=f"/api/v1/github/{customer_id}/")
        return cls(client=client)

    def __init__(self, *, client: httpx.Client) -> None:
        self._client = client

    def get_repos(self) -> tuple[GithubRepoInfo, ...]:
        response = self._client.get("")
        # TODO: Error handling
        response.raise_for_status()
        repos_json = response.json()["results"]
        return tuple(GithubRepoInfo.from_response(repo_json) for repo_json in repos_json)

    def get_install_info(self) -> InstallInfo:
        response = self._client.options("")
        # TODO: Error handling
        response.raise_for_status()
        return InstallInfo.from_response(response.json()["data"])
