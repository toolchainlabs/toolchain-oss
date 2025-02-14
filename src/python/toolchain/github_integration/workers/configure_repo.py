# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import random

from django.conf import settings

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Repo
from toolchain.github_integration.app_client import (
    GithubRepoClient,
    MissingGithubPermissionsError,
    Webhook,
    get_repo_client,
)
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class GithubRepoConfigurator(Worker):
    work_unit_payload_cls = ConfigureGithubRepo
    # https://docs.github.com/en/free-pro-team@latest/developers/webhooks-and-events/webhook-events-and-payloads
    REPO_EVENTS = (
        "pull_request",
        "push",
        "create",
        "check_run",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._webhook_url = settings.REPO_WEBHOOK_URL
        self._toolchain_url_match = settings.TOOLCHAIN_WEBHOOK_EXPRESSION

    def do_work(self, work_unit_payload: ConfigureGithubRepo) -> bool:
        gh_repo = GithubRepo.get_by_id(work_unit_payload.repo_id)
        if not gh_repo:
            raise ToolchainAssertion(f"Unknown GithubRepo: {work_unit_payload.repo_id}")
        repo = Repo.get_by_slug_and_customer_id(
            customer_id=gh_repo.customer_id, slug=gh_repo.name, include_inactive=True
        )
        if not repo:
            raise ToolchainAssertion(f"Unknown Repo for Github repo: {gh_repo}")
        gh_repo.set_state(repo.is_active)
        if gh_repo.is_active:
            self._connect_repo(
                gh_repo,
                repo_events=self.REPO_EVENTS + work_unit_payload.extra_events,
                force_update=work_unit_payload.force_update,
            )
        else:
            self._disconnect_repo(gh_repo)
        return True

    def _disconnect_repo(self, repo: GithubRepo) -> None:
        try:
            client = get_repo_client(repo, allow_inactive=True)
        except MissingGithubPermissionsError:
            _logger.warning(f"We no longer have access to repo: {repo}")
            return
        toolchain_webhook = self._get_toolchain_webhook(client)
        if not toolchain_webhook:
            _logger.info(f"Not Toolchain webhook for {repo}")
            return
        _logger.info(f"delete_webhook {repo=} webhook_id={toolchain_webhook.webhook_id}")
        client.delete_webhook(webhook_id=toolchain_webhook.webhook_id)

    def _get_toolchain_webhook(self, client: GithubRepoClient) -> Webhook | None:
        webhooks = client.list_webhooks()
        for webhook in webhooks:
            if self._toolchain_url_match.match(webhook.url):
                return webhook
        return None

    def _connect_repo(self, github_repo: GithubRepo, repo_events: tuple[str, ...], force_update: bool) -> None:
        client = get_repo_client(github_repo)
        toolchain_webhook = self._get_toolchain_webhook(client)
        _logger.info(f"connect_github_repo {github_repo=} webhook_exists={bool(toolchain_webhook)}")
        if not toolchain_webhook:
            webhook = client.create_webhook(
                url=self._webhook_url, secret=github_repo.webhooks_secret, events=repo_events
            )
            _logger.info(f"create_webhook {github_repo=} webhook={self._webhook_url} webhook_id={webhook.webhook_id}")
            return
        if not force_update:
            events_identical = set(repo_events) == set(toolchain_webhook.events)
            if toolchain_webhook.active and events_identical and toolchain_webhook.url == self._webhook_url:
                _logger.info(
                    f"no need to update webhook for {github_repo=} webhook_id={toolchain_webhook.webhook_id} old_url={toolchain_webhook.url}"
                )
                return
        webhook = client.update_webhook(
            webhook_id=toolchain_webhook.webhook_id,
            url=self._webhook_url,
            secret=github_repo.webhooks_secret,
            events=repo_events,
        )
        _logger.info(
            f"update_webhook {github_repo=} webhook_id={toolchain_webhook.webhook_id} old_url={toolchain_webhook.url} webhook={self._webhook_url} {force_update=} {repo_events=}"
        )

    def on_reschedule(self, work_unit_payload: ConfigureGithubRepo) -> datetime.datetime | None:
        work_unit_payload.disable_force_update()
        # some randomness so we don't end up running a bunch of those at the same time
        return utcnow() + datetime.timedelta(days=5, minutes=random.randint(3, 900))

    def on_success(self, work_unit_payload: ConfigureGithubRepo) -> None:
        work_unit_payload.disable_force_update()
