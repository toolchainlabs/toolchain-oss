# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections.abc import Sequence
from dataclasses import dataclass

import httpx
from dateutil.parser import parse
from django.conf import settings
from jose import jwt
from prometheus_client import Histogram

from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError, ToolchainTransientError
from toolchain.django.site.models import Customer
from toolchain.github_integration.config import GithubIntegrationConfig
from toolchain.github_integration.constants import DataSource, GithubActionsWorkflowRun
from toolchain.github_integration.models import GithubRepo

_logger = logging.getLogger(__name__)


class MissingGithubPermissionsError(ToolchainError):
    pass


class GithubServerError(ToolchainTransientError):
    pass


GITHUB_API_LATENCY = Histogram(
    name="toolchain_github_api_latency",
    documentation="Histogram of GitHub API calls latency.",
    labelnames=["api", "method", "status_code"],
    buckets=(0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1, 1.5, 3, 4, 5, 8, 10, 15, 20, float("inf")),
)


@dataclass(frozen=True)
class GithubOrgInfo:
    slug: str
    name: str

    @classmethod
    def from_payload(cls, org_info_json: dict) -> GithubOrgInfo:
        slug = org_info_json["login"]
        return cls(slug=slug, name=org_info_json["name"] or slug)

    @classmethod
    def default_for_slug(cls, slug: str) -> GithubOrgInfo:
        return cls(slug=slug, name=slug)


@dataclass
class AccessToken:
    token: str
    expires_at: datetime.datetime
    permissions: dict[str, str]

    @classmethod
    def from_response(cls, response_json: dict) -> AccessToken:
        # https://developer.github.com/v3/apps/#response-7
        expires_at = parse(response_json["expires_at"])
        return cls(token=response_json["token"], expires_at=expires_at, permissions=response_json["permissions"])


@dataclass(frozen=True)
class Webhook:
    webhook_id: str  # it is an int, but storing as string since it doesn't have numerical meaning
    active: bool
    events: tuple[str, ...]
    created_at: datetime.datetime
    hook_type: str
    url: str

    @classmethod
    def from_response(cls, json_data: dict) -> Webhook:
        config = json_data["config"]
        return cls(
            webhook_id=str(json_data["id"]),
            active=json_data["active"],
            events=tuple(json_data["events"]),
            created_at=parse(json_data["created_at"]),
            hook_type=json_data["type"],
            url=config["url"],
        )


class PermissionsSets:
    # https://developer.github.com/apps/building-github-apps/creating-github-apps-using-url-parameters/#github-app-permissions
    REPO = {"repository_hooks": "write", "administration": "read", "metadata": "read", "actions": "read"}


class BaseGithubClient:
    ACCEPT = "application/vnd.github.machine-man-preview+json"

    def __init__(self, timeout: int | None = None) -> None:
        token = self.get_token()
        self._client = httpx.Client(
            base_url="https://api.github.com/",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": self.ACCEPT,
                "User-Agent": "integration(Toolchain.com)",
            },
            timeout=timeout or 3,
            transport=httpx.HTTPTransport(retries=3),
        )

    def get_token(self) -> str:
        """Must be implemented by subclasses."""
        raise NotImplementedError

    def _handle_response(self, api_name: str, response, timer, context: str | None = None) -> None:
        GITHUB_API_LATENCY.labels(
            api=api_name, method=response.request.method, status_code=response.status_code
        ).observe(timer.elapsed)
        _logger.info(
            f"github_api_request {api_name=} status={response.status_code} elapsed={timer.elapsed:.3f}sec url={response.url} {context or ''}"
        )
        if not response.is_error:
            return
        request_id = response.headers.get("X-GitHub-Request-Id", "NA")
        context_str = f" {context} " if context else " "
        _logger.warning(
            f"github_request_failed {api_name=} url={response.url}{context_str}{request_id=} status={response.status_code} {response.text}"
        )
        if 599 >= response.status_code >= 500:  # GitHub Server errors (HTTP 5xx)
            # HTTP 50x error - github trainsient error or outage.
            raise GithubServerError(f"{response} - {response.read().decode()}")
        response.raise_for_status()

    def do_get_request(
        self,
        api_name: str,
        path: str,
        error_on_404: bool = True,
        params: dict | None = None,
        context: str | None = None,
    ) -> dict:
        with Timer() as timer:
            response = self._client.get(path, params=params)
        if response.status_code == 404 and not error_on_404:
            return {}  # we want to avoid returning None because it makes mypy mad.

        self._handle_response(api_name, response, timer, context=context)
        return response.json()

    def do_delete_request(self, api_name: str, path: str) -> None:
        with Timer() as timer:
            response = self._client.delete(path)
        self._handle_response(api_name, response, timer)

    def do_post_request(self, api_name: str, path: str, json_params: dict) -> dict:
        with Timer() as timer:
            response = self._client.post(path, json=json_params)
        self._handle_response(api_name, response, timer)
        return response.json()

    def do_patch_request(self, api_name: str, path: str, json_params: dict) -> dict:
        with Timer() as timer:
            response = self._client.patch(path, json=json_params)
        self._handle_response(api_name, response, timer)
        return response.json()


class GithubAppClient(BaseGithubClient):
    @classmethod
    def for_config(cls, config: GithubIntegrationConfig, timeout: int | None = None) -> GithubAppClient:
        return cls(app_id=config.app_id, private_key=config.private_key, timeout=timeout)

    def __init__(self, *, app_id: str, private_key: bytes, timeout: int | None) -> None:
        self._app_id = app_id
        self._private_key = private_key
        super().__init__(timeout)

    def get_token(self) -> str:
        # https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-a-github-app
        now = utcnow()
        payload = {
            "iat": now,
            "exp": now + datetime.timedelta(minutes=7),
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def list_installations(self) -> list[dict]:
        # Currently, we don't have logic using this API, however it is useful for debugging in a django shell
        # We will eventually have logic to periodically call it and sync stuff in case we miss web hooks.
        # https://developer.github.com/v3/apps/#list-installations-for-the-authenticated-app
        return self.do_get_request("list_installations", "app/installations")  # type: ignore[return-value]

    def get_installation_access_token(
        self, installation_id: str, repo_ids: list[int], permissions: dict
    ) -> AccessToken:
        # https://developer.github.com/v3/apps/#create-an-installation-access-token-for-an-app
        path = f"app/installations/{installation_id}/access_tokens"
        params = {"repository_ids": repo_ids, "permissions": permissions}
        try:
            response = self.do_post_request("get_installation_access_token", path, json_params=params)
        except httpx.HTTPStatusError as error:
            error_response = error.response
            _logger.warning(
                f"HTTP error {error_response.status_code} on get_installation_access_token: {error_response.text}"
            )
            if error_response.status_code in {422, 404}:
                raise MissingGithubPermissionsError(str(error_response))
            raise
        except httpx.TransportError as error:
            _logger.warning(f"transport error on get_installation_access_token: {error!r}")
            raise GithubServerError(f"Transport error getting token from GitHub: {error}")
        return AccessToken.from_response(response)


class GithubRepoClient(BaseGithubClient):
    ISSUES_PAGE_SIZE = 100

    def __init__(
        self, *, owner_slug: str, repo_slug: str, access_token: AccessToken, timeout: int | None = None
    ) -> None:
        self._owner = owner_slug
        self._repo = repo_slug
        self._access_token = access_token
        super().__init__(timeout)

    def get_token(self) -> str:
        return self._access_token.token

    def get_repo_info(self) -> dict:
        # https://docs.github.com/en/rest/reference/repos#get-a-repository
        path = f"repos/{self._owner}/{self._repo}"
        return self.do_get_request("get_repo_info", path)

    def get_repo_views(self) -> dict:
        # https://docs.github.com/en/rest/reference/metrics#get-page-views
        path = f"repos/{self._owner}/{self._repo}/traffic/views"
        return self.do_get_request("get_repo_views", path)

    def get_clones(self) -> dict:
        # https://docs.github.com/en/rest/reference/metrics#get-repository-clones
        path = f"repos/{self._owner}/{self._repo}/traffic/clones"
        return self.do_get_request("get_clones", path)

    def get_popular_referral_paths(self) -> dict:
        # https://docs.github.com/en/rest/reference/metrics#get-top-referral-paths
        path = f"repos/{self._owner}/{self._repo}/traffic/popular/paths"
        return self.do_get_request("get_popular_referral_paths", path)

    def get_popular_referral_sources(self) -> dict:
        # https://docs.github.com/en/rest/reference/metrics#get-top-referral-sources
        path = f"repos/{self._owner}/{self._repo}/traffic/popular/referrers"
        return self.do_get_request("get_popular_referral_sources", path)

    def list_webhooks(self) -> tuple[Webhook, ...]:
        # https://developer.github.com/v3/repos/hooks/#list-repository-webhooks
        path = f"repos/{self._owner}/{self._repo}/hooks"
        resp_json = self.do_get_request("list_webhooks", path)
        return tuple(Webhook.from_response(hook) for hook in resp_json)

    def delete_webhook(self, webhook_id: str) -> None:
        # https://developer.github.com/v3/repos/hooks/#delete-a-repository-webhook
        if not webhook_id:
            raise ToolchainAssertion("webhook_id can't be empty")
        self.do_delete_request("delete_webhook", f"repos/{self._owner}/{self._repo}/hooks/{webhook_id}")

    def update_webhook(self, webhook_id: str, url: str, secret: str, events: Sequence[str]) -> Webhook:
        # https://developer.github.com/v3/repos/hooks/#update-a-repository-webhook
        if not webhook_id:
            raise ToolchainAssertion("webhook_id can't be empty")
        json_params = {
            "active": True,
            "events": list(events),
            "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": 0},
        }
        path = f"repos/{self._owner}/{self._repo}/hooks/{webhook_id}"
        resp_json = self.do_patch_request("update_webhook", path, json_params=json_params)
        return Webhook.from_response(resp_json)

    def create_webhook(self, *, url: str, secret: str, events: Sequence[str]) -> Webhook:
        # https://developer.github.com/v3/repos/hooks/#create-a-repository-webhook
        if not secret:
            raise ToolchainAssertion("Invalid webhook secret")
        path = f"repos/{self._owner}/{self._repo}/hooks"
        json_params = {
            "name": "web",
            "active": True,
            "events": list(events),
            "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": 0},
        }
        resp_json = self.do_post_request("create_webhook", path, json_params=json_params)
        return Webhook.from_response(resp_json)

    def get_workflow_actions_run(self, run_id: str) -> tuple[GithubActionsWorkflowRun, dict] | tuple[None, None]:
        # https://docs.github.com/en/rest/reference/actions#get-a-workflow-run
        path = f"repos/{self._owner}/{self._repo}/actions/runs/{run_id}"
        try:
            resp_json = self.do_get_request("get_workflow_actions_run", path, error_on_404=False)
        except httpx.TransportError as error:
            _logger.warning(f"transport error on get_workflow_actions_run: {error!r}")
            resp_json = None
        if not resp_json:
            return None, None
        actions_run = GithubActionsWorkflowRun.from_json_dict(
            source=DataSource.API, fetch_time=utcnow(), json_data=resp_json
        )
        return actions_run, resp_json

    def list_issues(self, page: int) -> list[dict]:
        # https://docs.github.com/en/rest/reference/issues#list-repository-issues
        resp_json = self.do_get_request(
            "list_issues",
            f"repos/{self._owner}/{self._repo}/issues",
            params={
                "state": "all",
                "sort": "created",
                "order": "desc",
                "per_page": self.ISSUES_PAGE_SIZE,
                "page": page,
            },
            context=f"{page=}",
        )
        return resp_json  # type: ignore[return-value]


def get_repo_client(repo: GithubRepo, timeout: int | None = None, allow_inactive: bool = False) -> GithubRepoClient:
    config = settings.GITHUB_CONFIG
    app_client = GithubAppClient.for_config(config)
    customer = Customer.get_for_id_or_none(customer_id=repo.customer_id, include_inactive=allow_inactive)
    if not customer:
        # we might hit this code path for inactive customers.
        # so we might have change Customer.get_or_none to return inactive customers
        raise ToolchainAssertion(f"{repo.customer_id=} is not valid")
    owner_slug = customer.slug  # for now assuming that the GH slug and the TC slug are the same.
    install_token = app_client.get_installation_access_token(
        installation_id=repo.install_id, repo_ids=[int(repo.repo_id)], permissions=PermissionsSets.REPO
    )
    return GithubRepoClient(owner_slug=owner_slug, repo_slug=repo.name, access_token=install_token, timeout=timeout)


def get_github_org_info(slug: str) -> GithubOrgInfo:
    try:
        resp = httpx.get(url=f"https://api.github.com/users/{slug}")
    except httpx.RequestError as err:
        _logger.warning(f"request Error to get org info for {slug=} {err!r}")
        return GithubOrgInfo.default_for_slug(slug)
    if not resp.is_success:
        _logger.warning(f"HTTP Error to get org info for {slug=} {resp.status_code=} {resp.text=}")
        return GithubOrgInfo.default_for_slug(slug)
    return GithubOrgInfo.from_payload(resp.json())
