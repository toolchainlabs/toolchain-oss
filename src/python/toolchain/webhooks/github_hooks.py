# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View

from toolchain.github_integration.client.app_clients import AppWebhookClient
from toolchain.github_integration.client.repo_clients import RepoWebhookClient
from toolchain.github_integration.common.records import GitHubEvent, InvalidGithubEvent

_logger = logging.getLogger(__name__)


def check_signature(*, secrets: tuple[bytes, ...], event: GitHubEvent) -> bool:
    attempted = []
    for secret in secrets:
        digest = hmac.new(secret, event.payload, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        match = event.signature == expected
        if match:
            return True
        attempted.append(expected)
    _logger.warning(f"invalid_signature received={event.signature} expected={attempted}")
    return False


class GithubAppWebhookView(View):
    view_type = "app"

    @classmethod
    def get_webhook_secrets(cls) -> tuple[bytes, ...]:
        return settings.WEBHOOKS_CONFIG.github_webhook_secrets

    def post(self, request):
        # TODO: check that content type is application/json
        # TODO: add metrics
        try:
            event = GitHubEvent.create(headers=request.headers, body=request.body)
        except InvalidGithubEvent as error:
            return self._reject_webhook("invalid_event", repr(error))
        if not check_signature(secrets=self.get_webhook_secrets(), event=event):
            return self._reject_webhook("invalid_signature")
        client = AppWebhookClient.for_settings(settings)
        client.post_github_webhook(event=event)
        return HttpResponse("OK")

    def _reject_webhook(self, reason: str, error: str = "") -> HttpResponse:
        _logger.warning(f"reject_github_app_webhook {reason=} {error}")
        # TODO: Add a metric/counter
        # TODO: block IP that gives us bad data for a while.
        return HttpResponse("OK")  # Don't let caller know the signature is bad.


class GithubRepoWebhookView(View):
    view_type = "app"

    def post(self, request) -> HttpResponse:
        event = GitHubEvent.create(headers=request.headers, body=request.body)
        # TODO: check that content type is application/json
        try:
            github_repo_id = int(event.json_payload["repository"]["id"])
        except (KeyError, ValueError) as error:
            return self._reject_webhook("missing_repo_id", f"{event.json_payload} {error!r}")
        if not github_repo_id:
            return self._reject_webhook("empty_repo_id", str(event.json_payload))
        repo_client = RepoWebhookClient.for_settings(settings)
        response = self._check_signature(repo_client, github_repo_id, event)
        if response:
            return response
        repo_client.post_github_webhook(github_repo_id=github_repo_id, event=event)
        return HttpResponse("OK")

    def _check_signature(
        self, client: RepoWebhookClient, github_repo_id: int, event: GitHubEvent
    ) -> HttpResponse | None:
        secret = client.get_webhook_secret(github_repo_id=github_repo_id)
        if not secret:
            return self._reject_webhook("no_secret", f"{github_repo_id=}")
        if not check_signature(secrets=(secret.encode(),), event=event):
            return self._reject_webhook("invalid_signature")
        return None

    def _reject_webhook(self, reason: str, error: str = "") -> HttpResponse:
        _logger.warning(f"reject_github_repo_webhook {reason=} {error}")
        # TODO: Add a metric/counter
        # TODO: block IP that gives us bad data for a while.
        return HttpResponse("OK")  # Don't let caller know the signature is bad.
