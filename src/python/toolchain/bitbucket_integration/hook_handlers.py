# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from jose import jwt
from jose.constants import ALGORITHMS

from toolchain.base.toolchain_error import ToolchainError
from toolchain.bitbucket_integration.common.events import WebhookEvent
from toolchain.bitbucket_integration.models import BitbucketAppInstall
from toolchain.bitbucket_integration.repo_data_store import BitbucketRepoDataStore
from toolchain.django.site.models import Repo

_logger = logging.getLogger(__name__)


class HookHandleFailure(ToolchainError):
    def __init__(self, message, critical: bool = False) -> None:
        super().__init__(message)
        self.critical = critical


def run_handler(webhook_event: WebhookEvent) -> bool:
    if webhook_event.event_type not in _EVENT_HANDLERS:
        raise HookHandleFailure(f"no handler for {webhook_event.event_type=}")
    handler = _EVENT_HANDLERS[webhook_event.event_type]
    if not handler:
        _logger.info(f"bitbucket_webhook_ignore event={webhook_event.event_type}")
        return False
    repo_json = webhook_event.json_payload["data"]["repository"]
    workspace = repo_json["workspace"]
    app_install = BitbucketAppInstall.for_account_id(workspace["uuid"])
    if not app_install:
        raise HookHandleFailure(f"No app install info for {workspace=} event={webhook_event.event_type}")
    payload_data = webhook_event.json_payload["data"]
    _logger.info(
        f"bitbucket_webhook event={webhook_event.event_type} app={app_install.account_name} keys={payload_data.keys()}"
    )
    token_str = webhook_event.jwt
    if not token_str:
        raise HookHandleFailure(f"missing JWT fo {webhook_event.event_type=}", critical=True)
    check_jwt(app_install, token_str)
    handler(webhook_event, app_install)
    return True


def check_jwt(installed_app: BitbucketAppInstall, token_str: str):
    try:
        claims = jwt.decode(
            token=token_str,
            key=installed_app.shared_secret,
            algorithms=ALGORITHMS.HS256,
            audience=installed_app.client_key,
            options={
                "require_iat": True,
                "require_exp": True,
                "require_iss": True,
                "require_aud": True,
            },
        )
    except jwt.JWTError as error:
        raise HookHandleFailure(f"Bad JWT: {error} for account={installed_app.account_name}", critical=True)
    return claims["iss"]


def _handle_pull_request(webhook_event: WebhookEvent, app_install: BitbucketAppInstall):
    repo_ds = _get_repo_data_store(webhook_event.json_payload["data"], customer_id=app_install.customer_id)
    repo_ds.save_pull_request(webhook_event.json_payload)


def _handle_push(webhook_event: WebhookEvent, app_install: BitbucketAppInstall):
    repo_ds = _get_repo_data_store(webhook_event.json_payload["data"], customer_id=app_install.customer_id)
    repo_ds.save_push(webhook_event.json_payload)


def _get_repo_data_store(payload_data: dict, customer_id: str) -> BitbucketRepoDataStore:
    slug = payload_data["repository"]["name"]
    repo_fn = payload_data["repository"]["full_name"]
    repo = Repo.get_by_slug_and_customer_id(customer_id=customer_id, slug=slug)
    if not repo:
        raise HookHandleFailure(f"no active repo for {repo_fn} {customer_id=}")
    return BitbucketRepoDataStore.for_repo(repo)


_EVENT_HANDLERS = {
    # None value means we explicitly choose to ignore the webhook.
    "pullrequest:created": _handle_pull_request,
    "pullrequest:updated": _handle_pull_request,
    "pullrequest:approved": None,
    "pullrequest:unapproved": None,
    "pullrequest:fulfilled": None,  # Merge PR
    "pullrequest:comment_deleted": None,
    "pullrequest:comment_created": None,
    "repo:push": _handle_push,
    "repo:commit_status_updated": None,
    "repo:commit_status_created": None,
}
