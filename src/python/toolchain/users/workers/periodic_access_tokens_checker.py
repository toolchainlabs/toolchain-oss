# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from django.conf import settings

from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import AllocatedRefreshToken, Repo, ToolchainUser
from toolchain.users.models import (
    PeriodicallyCheckAccessTokens,
    PeriodicallyNotifyExpringTokens,
    PeriodicallyRevokeTokens,
)
from toolchain.util.internal_emails.internal_email_helper import SendEmailHelper
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PeriodicAccessTokensChecker(Worker):
    work_unit_payload_cls = PeriodicallyCheckAccessTokens

    def do_work(self, payload: PeriodicallyCheckAccessTokens) -> bool:
        self._deactivate_tokens()
        self._delete_expired_tokens()
        if payload.period_minutes is None:
            # We were a one-time processing
            return True
        # Note that if we're not a one-time processing we never succeed, but keep scheduling the checker forever.
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyCheckAccessTokens) -> datetime.datetime | None:
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)

    def _deactivate_tokens(self) -> None:
        threshold = utcnow()
        count = AllocatedRefreshToken.deactivate_expired_tokens(threshold)
        if count:
            _logger.info(f"expired_tokens={count} deactivated.")

    def _delete_expired_tokens(self) -> None:
        threshold = utcnow() - datetime.timedelta(days=30)
        qs = AllocatedRefreshToken.get_expired_or_revoked_tokens(expiration_deletetion_threshold=threshold)
        count = qs.count()
        if count:
            _logger.info(f"expired_or_revoked_tokens={count} deleted")
        qs.delete()


class PeriodicTokenRevoker(Worker):
    work_unit_payload_cls = PeriodicallyRevokeTokens
    USERS_BATCH_SIZE = 30

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tokens_to_revoke: list[AllocatedRefreshToken] = []

    def _collect_tokens(self, max_tokens: int) -> list[AllocatedRefreshToken]:
        tokens: list[AllocatedRefreshToken] = []
        for inactive_user_api_ids_batch in self._iter_user_api_ids_batches():
            tokens.extend(AllocatedRefreshToken.get_active_tokens_for_users(user_api_ids=inactive_user_api_ids_batch))
            if len(tokens) >= max_tokens:
                break
        return tokens[:max_tokens]

    def _iter_user_api_ids_batches(self) -> Iterator[tuple[str, ...]]:
        inactive_user_api_ids_batch = []
        for user_api_id in ToolchainUser.get_inactive_users_api_ids():
            inactive_user_api_ids_batch.append(user_api_id)
            if len(inactive_user_api_ids_batch) < self.USERS_BATCH_SIZE:
                continue
            yield tuple(inactive_user_api_ids_batch)
            inactive_user_api_ids_batch.clear()
        if inactive_user_api_ids_batch:
            yield tuple(inactive_user_api_ids_batch)

    def do_work(self, work_unit_payload: PeriodicallyRevokeTokens) -> bool:
        payload: PeriodicallyRevokeTokens = work_unit_payload
        self._tokens_to_revoke.extend(self._collect_tokens(payload.max_tokens))
        # Note that if we're not a one-time processing we never succeed, but keep scheduling the checker forever.
        return payload.period_minutes is None

    def on_success(self, work_unit_payload: PeriodicallyRevokeTokens) -> None:
        self._deactivate_tokens()

    def on_reschedule(self, work_unit_payload: PeriodicallyRevokeTokens) -> datetime.datetime:
        self._deactivate_tokens()
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)

    def _deactivate_tokens(self) -> None:
        if not self._tokens_to_revoke:
            return
        _logger.info(f"tokens_to_revoke={len(self._tokens_to_revoke)}")
        for token in self._tokens_to_revoke:
            token.revoke()


class PeriodicNotifyExpiringTokensExpiration(Worker):
    work_unit_payload_cls = PeriodicallyNotifyExpringTokens
    TARGET_EMAIL_ADDRESS = settings.TARGET_EMAIL_ADDRESS
    # Same as the plugin (src/python/toolchain/pants/auth/client.py) + 1 day
    # so we get notified internally (end eventually the customer) before the the plugin starts to print
    # the warning
    TOKEN_EXPIRATION_WARNING_WINDOW = datetime.timedelta(days=10) + datetime.timedelta(days=1)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._notifications: dict[ToolchainUser, str] = {}
        self._email_helper = SendEmailHelper(Path(__file__).parent / "email_templates")

    def do_work(self, work_unit_payload: PeriodicallyCheckAccessTokens):
        expiring_user_tokens = self._get_expiring_tokens_by_users()
        if expiring_user_tokens:
            self._notifications = self._prepare_notifications(expiring_user_tokens)
        # Note that if we're not a one-time processing we never succeed, but keep scheduling the checker forever.
        return work_unit_payload.period_minutes is None

    def on_success(self, work_unit_payload: PeriodicallyCheckAccessTokens) -> None:
        self._dispatch_notifications(self._notifications)

    def on_reschedule(self, work_unit_payload: PeriodicallyCheckAccessTokens) -> datetime.datetime:
        self._dispatch_notifications(self._notifications)
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)

    def _dispatch_notifications(self, notifications: dict[ToolchainUser, str]) -> None:
        if not notifications:
            return
        # for now, we just write the notification to the log.
        # we will do something better with them down the line.
        _logger.info(f"Notify {len(notifications)} users on expiring tokens.")
        lines = []
        for user, msg in notifications.items():
            lines.append(f"{user.username} {user.email} - {msg}")
        unified_msg = "\n".join(lines)
        _logger.info(f"expiring_ci_tokens: {unified_msg}")
        self._email_helper.send_email(
            email_address=self.TARGET_EMAIL_ADDRESS,
            subject="Expiring CI tokens for customers",
            template_name="expiring_customer_ci_tokens.html",
            context={"notifications": notifications},
        )

    def _get_expiring_tokens_by_users(self) -> dict[str, list[AllocatedRefreshToken]]:
        now = utcnow()
        past_two_weeks = now - datetime.timedelta(days=14)
        next_week = now + self.TOKEN_EXPIRATION_WARNING_WINDOW
        tokens = AllocatedRefreshToken.get_expiring_api_tokens(
            last_used_threshold=past_two_weeks, expiring_on=next_week
        )
        # We only notify about expiring CI tokens, since for tokens used on the desktop the user sees errors from the plugin.
        ci_tokens = [token for token in tokens if token.audiences and token.audiences.can_impersonate]
        _logger.info(f"Expiring CI tokens {len(ci_tokens)} out of {len(tokens)} expiring tokens.")
        if not ci_tokens:
            return {}
        expiring_user_tokens = defaultdict(list)
        for token in ci_tokens:
            expiring_user_tokens[token.user_api_id].append(token)
        return expiring_user_tokens

    def _prepare_notifications(self, users_tokens: dict[str, list[AllocatedRefreshToken]]) -> dict[ToolchainUser, str]:
        users_iter = ToolchainUser.with_api_ids(users_tokens.keys(), include_inactive=False)  # type:ignore[arg-type]
        users_map = {user.api_id: user for user in users_iter}
        notifications: dict[ToolchainUser, str] = {}
        for user_api_id, tokens in users_tokens.items():
            user = users_map.get(user_api_id)
            if not user:
                _logger.warning(f"User {user_api_id} not active - will not notify about tokens: {tokens}")
                continue
            message = self._generate_notification_for_tokens(tokens)
            if message:
                notifications[user] = message
        return notifications

    def _generate_notification_for_tokens(self, tokens: list[AllocatedRefreshToken]) -> str:
        repo_ids = {token.repo_id for token in tokens if token.repo_id}
        repo_map = {repo.id: repo for repo in Repo.with_api_ids(repo_ids=repo_ids)}
        messages = []
        for token in sorted(tokens, key=lambda token: token.expires_at):
            if not token.repo_id:
                _logger.warning(f"no repo associated with: {token}")
                continue
            repo = repo_map.get(token.repo_id)
            if not repo:
                _logger.warning(f"Repo {token.repo_id} associated with: {token} is N/A")
                continue
            messages.append(
                f"Repo: {repo.customer.slug}/{repo.slug} description: {token.description} expires at: {token.expires_at.date().isoformat()} last used: {token.last_seen.date().isoformat()}"
            )
        # For most users, in most cases len(messages) == 1.
        return ", ".join(messages)
