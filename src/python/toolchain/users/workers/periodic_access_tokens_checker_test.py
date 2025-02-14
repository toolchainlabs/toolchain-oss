# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from collections.abc import Sequence

import pytest
from moto import mock_ses

from toolchain.aws.test_utils.ses_utils import get_ses_sent_messages, get_ses_sent_messages_count, verify_ses_email
from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import AccessTokenState, AllocatedRefreshToken, Customer, Repo, ToolchainUser
from toolchain.users.models import (
    PeriodicallyCheckAccessTokens,
    PeriodicallyNotifyExpringTokens,
    PeriodicallyRevokeTokens,
)
from toolchain.users.workers.users_worker import UsersWorkDispatcher
from toolchain.util.test.util import assert_messages
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests
from toolchain.workflow.work_dispatcher import WorkDispatcher


def _count_by_state(state: AccessTokenState) -> int:
    return AllocatedRefreshToken.objects.filter(_token_state=state.value).count()


def _generate_tokens(
    user: ToolchainUser,
    num_of_tokens: int,
    issued_at: datetime.datetime,
    expiration_base: datetime.datetime,
    audience: AccessTokenAudience = AccessTokenAudience.CACHE_RO | AccessTokenAudience.BUILDSENSE_API,
    repo_id: str = "bobby",
) -> tuple[AllocatedRefreshToken, ...]:
    tokens_ids = []
    for i in range(num_of_tokens):
        expires_at = expiration_base + datetime.timedelta(hours=i + 2)
        tokens_ids.append(
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=expires_at,
                description=f"tinsel-{i}",
                repo_id=repo_id,
                audience=audience,
            )
        )
    return tuple(AllocatedRefreshToken.objects.filter(id__in=tokens_ids))


@pytest.mark.django_db()
class BaseWorkerTests(BaseWorkflowWorkerTests):
    def get_dispatcher(self) -> type[WorkDispatcher]:
        return UsersWorkDispatcher


class TestPeriodicAccessTokensChecker(BaseWorkerTests):
    def test_do_work_once(self) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=18)
        user = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        _generate_tokens(user, 2, now, now + datetime.timedelta(days=1))  # valid_tokens
        _generate_tokens(user, 6, issued_at, issued_at + datetime.timedelta(minutes=8))  # expired_tokens
        assert _count_by_state(AccessTokenState.ACTIVE) == 8
        assert _count_by_state(AccessTokenState.EXPIRED) == 0
        PeriodicallyCheckAccessTokens.objects.create(period_minutes=None)
        assert self.do_work() == 1
        work_unit = PeriodicallyCheckAccessTokens.objects.first().work_unit
        assert work_unit.state == WorkUnit.SUCCEEDED
        assert _count_by_state(AccessTokenState.ACTIVE) == 2
        assert _count_by_state(AccessTokenState.EXPIRED) == 6

    def test_periodic(self) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=18)
        user = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        _generate_tokens(user, 3, now, now + datetime.timedelta(days=1))  # valid_tokens
        _generate_tokens(user, 2, issued_at, issued_at + datetime.timedelta(minutes=8))  # expired_tokens
        assert _count_by_state(AccessTokenState.ACTIVE) == 5
        assert _count_by_state(AccessTokenState.EXPIRED) == 0
        PeriodicallyCheckAccessTokens.create_or_update(period_minutes=187)
        assert self.do_work() == 1
        work_unit = PeriodicallyCheckAccessTokens.objects.first().work_unit
        assert work_unit.state == WorkUnit.LEASED
        assert _count_by_state(AccessTokenState.ACTIVE) == 3
        assert _count_by_state(AccessTokenState.EXPIRED) == 2


class TestPeriodicTokenRevoker(BaseWorkerTests):
    def test_do_work_once(self) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=8)
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        _generate_tokens(user_1, 8, issued_at, now + datetime.timedelta(days=1))
        _generate_tokens(user_2, 5, issued_at, now + datetime.timedelta(days=1))
        user_2.deactivate()
        assert _count_by_state(AccessTokenState.ACTIVE) == 13
        assert _count_by_state(AccessTokenState.REVOKED) == 0
        PeriodicallyRevokeTokens.objects.create(period_minutes=None, max_tokens=2)
        assert self.do_work() == 1
        work_unit = PeriodicallyRevokeTokens.objects.first().work_unit
        assert work_unit.state == WorkUnit.SUCCEEDED
        assert _count_by_state(AccessTokenState.ACTIVE) == 11
        assert _count_by_state(AccessTokenState.REVOKED) == 2

    def test_periodic(self) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=9)
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        _generate_tokens(user_1, 3, issued_at, now + datetime.timedelta(days=1))
        _generate_tokens(user_2, 8, issued_at, now + datetime.timedelta(days=1))
        user_2.deactivate()
        assert _count_by_state(AccessTokenState.ACTIVE) == 11
        assert _count_by_state(AccessTokenState.REVOKED) == 0
        PeriodicallyRevokeTokens.create_or_update(period_minutes=74, max_tokens=20)
        assert self.do_work() == 1
        work_unit = PeriodicallyRevokeTokens.objects.first().work_unit
        assert work_unit.state == WorkUnit.LEASED
        assert _count_by_state(AccessTokenState.ACTIVE) == 3
        assert _count_by_state(AccessTokenState.REVOKED) == 8


class TestPeriodicNotifyExpringTokensExpiration(BaseWorkerTests):
    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_ses():
            verify_ses_email("devinfra@toolchain.com")
            yield

    def _use_tokens(self, tokens: Sequence[AllocatedRefreshToken], used_at: datetime.datetime) -> None:
        for token in tokens:
            token.last_seen = used_at
            token.save()

    def _get_notifications(self, caplog) -> list[str]:
        lr = assert_messages(caplog, match="expiring_ci_tokens")
        notifications = lr.message.replace("expiring_ci_tokens: ", "").splitlines()  # type: ignore[union-attr]
        return notifications

    def _assert_sent_email(self) -> str:
        assert get_ses_sent_messages_count() == 1
        msg = get_ses_sent_messages()[0]
        assert msg.subject == "Expiring CI tokens for customers"
        assert msg.source == "devinfra@toolchain.com"
        assert msg.destinations == {
            "ToAddresses": ["jerry-seinfeld-fake@toolchain.com"],
            "CcAddresses": [],
            "BccAddresses": [],
        }
        return msg.body

    def test_expiring_unused_tokens(self) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=120)
        PeriodicallyNotifyExpringTokens.create_or_update(period_minutes=6)
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        _generate_tokens(user_1, 3, issued_at, now + datetime.timedelta(days=1))
        _generate_tokens(user_2, 8, issued_at, now + datetime.timedelta(days=1))
        assert self.do_work() == 1
        assert get_ses_sent_messages_count() == 0
        wu = PeriodicallyNotifyExpringTokens.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED

    @pytest.fixture()
    def repo(self) -> Repo:
        customer = Customer.create("festivus", name="Festivus to the rest of us")
        return Repo.create("tinsel", customer, "Tinsel Repo")

    def test_expiring_used_tokens_not_ci_tokens(self, caplog, repo: Repo) -> None:
        now = utcnow()
        yesterday = now - datetime.timedelta(days=1)
        issued_at = now - datetime.timedelta(days=120)
        expires_base = now + datetime.timedelta(days=1)
        PeriodicallyNotifyExpringTokens.create_or_update(period_minutes=6)
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_1_tokens = _generate_tokens(user_1, 3, issued_at, expires_base)
        user_2_tokens = _generate_tokens(user_2, 8, issued_at, expires_base)
        self._use_tokens(user_1_tokens + user_2_tokens, yesterday)
        assert self.do_work() == 1
        assert get_ses_sent_messages_count() == 0
        wu = PeriodicallyNotifyExpringTokens.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED
        wu = PeriodicallyNotifyExpringTokens.objects.first().work_unit
        assert wu.state == WorkUnit.LEASED

    def _setup_tokens(self, repo: Repo) -> tuple[ToolchainUser, ToolchainUser, datetime.datetime, datetime.datetime]:
        now = utcnow()
        last_used = now - datetime.timedelta(days=1)
        issued_at = now - datetime.timedelta(days=120)
        expires_base = (now + datetime.timedelta(days=1)).replace(hour=1)
        PeriodicallyNotifyExpringTokens.create_or_update(period_minutes=6)
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_1_tokens = _generate_tokens(
            user_1,
            3,
            issued_at,
            expires_base,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
            repo_id=repo.id,
        )
        user_2_tokens = _generate_tokens(
            user_2,
            8,
            issued_at,
            expires_base,
            audience=AccessTokenAudience.CACHE_RW | AccessTokenAudience.IMPERSONATE,
            repo_id=repo.id,
        )
        self._use_tokens(user_1_tokens[2:], last_used)
        self._use_tokens(user_2_tokens[4:6], last_used)
        return user_1, user_2, expires_base, last_used

    def test_expiring_used_tokens(self, caplog, repo: Repo) -> None:
        user_1, _, expires_base, last_used = self._setup_tokens(repo)
        now = utcnow()
        tomorrow = now - datetime.timedelta(days=1)
        yesterday = now - datetime.timedelta(days=1)
        legacy_token_id = AllocatedRefreshToken.allocate_api_token(  # old/legacy token w/o repo_id
            user_api_id=user_1.api_id,
            issued_at=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            expires_at=tomorrow,
            description="no soup for you",
            repo_id=None,  # type: ignore[arg-type]
            audience=AccessTokenAudience.CACHE_RW | AccessTokenAudience.IMPERSONATE,
        )
        self._use_tokens([AllocatedRefreshToken.objects.get(id=legacy_token_id)], yesterday)
        assert self.do_work() == 1
        notifications = set(self._get_notifications(caplog))
        expiration_str = expires_base.date().isoformat()
        last_used_str = last_used.date().isoformat()
        assert notifications == {
            f"jerry jerry@seinfeld.com - Repo: festivus/tinsel description: tinsel-4 expires at: {expiration_str} last used: {last_used_str}, Repo: festivus/tinsel description: tinsel-5 expires at: {expiration_str} last used: {last_used_str}",
            f"kenny kenny@seinfeld.com - Repo: festivus/tinsel description: tinsel-2 expires at: {expiration_str} last used: {last_used_str}",
        }
        self._assert_sent_email()

    def test_expiring_used_tokens_inactive_user(self, caplog, repo: Repo) -> None:
        _, user_2, expires_base, last_used = self._setup_tokens(repo)
        user_2.deactivate()
        assert self.do_work() == 1
        notifications = set(self._get_notifications(caplog))
        expiration_str = expires_base.date().isoformat()
        last_used_str = last_used.date().isoformat()
        assert notifications == {
            f"kenny kenny@seinfeld.com - Repo: festivus/tinsel description: tinsel-2 expires at: {expiration_str} last used: {last_used_str}"
        }
        self._assert_sent_email()

    def test_expiring_used_tokens_inactive_repo(self, caplog, repo: Repo) -> None:
        self._setup_tokens(repo)
        repo.deactivate()
        assert self.do_work() == 1
        assert get_ses_sent_messages_count() == 0
