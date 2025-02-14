# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.github_integration.common.records import GitHubEvent
from toolchain.github_integration.repo_data_store import GithubRepoDataStore

_logger = logging.getLogger(__name__)


_PR_ACTIONS_TO_HANDLE = {"opened", "edited", "closed", "reopened", "synchronize"}
# We don't expect the APP ID for the github actions to change. If it ever changes it will break the mechanism implemented in _handle_check_run_event
_KNOWN_GITHUB_ACTIONS_APP_ID = 15368


def _get_store(github_event: GitHubEvent, context: str) -> GithubRepoDataStore | None:
    data = github_event.json_payload
    github_repo_id = data["repository"]["id"]
    full_name = data["repository"]["full_name"]
    store = GithubRepoDataStore.for_github_repo_id(github_repo_id)
    if store:
        return store
    _logger.warning(f"No GitHub repo for {github_repo_id=} {full_name} {context}")
    # TODO: metrics, we should probably alert on this.
    return None


def _handle_check_run_event(github_event: GitHubEvent) -> bool:
    check_run = github_event.json_payload["check_run"]
    repo_full_name = github_event.json_payload["repository"]["full_name"]
    check_name = check_run["name"]
    app_slug = check_run["app"]["slug"]
    app_id = check_run["app"]["id"]
    # We only care about check runs for github actions
    if app_slug != "github-actions" or app_id != _KNOWN_GITHUB_ACTIONS_APP_ID:
        _logger.info(f"ignore check_run={check_name} for {repo_full_name} app={app_slug} {app_id=}")
        return False
    store = _get_store(github_event, check_run["html_url"])
    if not store:
        return False
    store.save_check_run(github_event.json_payload)
    return True


def _handle_pull_request_event(github_event: GitHubEvent) -> bool:
    # https://developer.github.com/webhooks/event-payloads/#pull_request
    data = github_event.json_payload
    if data["action"] not in _PR_ACTIONS_TO_HANDLE:
        return False
    store = _get_store(github_event, data["pull_request"]["html_url"])
    if not store:
        return False
    store.save_pull_request_from_webhook(data)
    return True


def _handle_issue_event(github_event: GitHubEvent) -> bool:
    # https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#issues
    data = github_event.json_payload
    store = _get_store(github_event, data["issue"]["html_url"])
    if not store:
        return False
    # See: https://docs.github.com/en/rest/reference/issues#list-repository-issues
    # Note: GitHub's REST API v3 considers every pull request an issue, but not every issue is a pull request.
    # For this reason, "Issues" endpoints may return both issues and pull requests in the response
    store.save_issue_from_webhook(data)
    return True


def _handle_push_event(github_event: GitHubEvent) -> bool:
    # https://developer.github.com/webhooks/event-payloads/#push
    data = github_event.json_payload
    head_commit = data.get("head_commit")
    if not head_commit:
        _logger.warning(f"Not handling push w/o head_commit: {data['ref']}")
        return False
    store = _get_store(github_event, head_commit["url"])
    if not store:
        return False
    return store.save_push(data)


def _log_hook(github_event: GitHubEvent) -> bool:
    _logger.info(f"EVENT={github_event.event_type} **PAYLOAD** {github_event.payload.decode()}")
    return True


REPO_EVENT_HANDLERS = {
    "pull_request": _handle_pull_request_event,
    "push": _handle_push_event,
    "check_run": _handle_check_run_event,
    "issues": _handle_issue_event,
}


def handle_github_repo_event(github_event: GitHubEvent) -> bool:
    handler = REPO_EVENT_HANDLERS.get(github_event.event_type)
    handled = handler(github_event) if handler else False
    _logger.info(f"GitHub Repo Webhook event={github_event.event_type}: {handled=}")
    return handled
