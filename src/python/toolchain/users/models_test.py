# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import re
from random import shuffle

import pytest
from django.http import Http404
from faker import Faker
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user, create_staff
from toolchain.users.models import (
    AccessTokenExchangeCode,
    AuthProvider,
    GithubRepoConfig,
    ImpersonationSession,
    InvalidAuthUser,
    OptionalBool,
    PeriodicallyCheckAccessTokens,
    PeriodicallyExportCustomers,
    PeriodicallyExportRemoteWorkerTokens,
    PeriodicallyNotifyExpringTokens,
    PeriodicallyRevokeTokens,
    RemoteExecWorkerToken,
    RestrictedAccessToken,
    UserAuth,
    UserCustomerAccessConfig,
    UserTermsOfServiceAcceptance,
)
from toolchain.workflow.models import WorkUnitPayload


@pytest.mark.django_db()
class TestPeriodicallyCheckAccessTokens:
    def test_create_new(self) -> None:
        assert PeriodicallyCheckAccessTokens.objects.count() == 0
        pct = PeriodicallyCheckAccessTokens.create_or_update(88)
        assert PeriodicallyCheckAccessTokens.objects.count() == 1
        loaded = PeriodicallyCheckAccessTokens.objects.first()
        assert loaded.period_minutes == 88
        assert loaded == pct

    def test_update_existing(self) -> None:
        assert PeriodicallyCheckAccessTokens.objects.count() == 0
        PeriodicallyCheckAccessTokens.create_or_update(88)
        assert PeriodicallyCheckAccessTokens.objects.count() == 1
        pct = PeriodicallyCheckAccessTokens.create_or_update(660)
        assert PeriodicallyCheckAccessTokens.objects.count() == 1
        loaded = PeriodicallyCheckAccessTokens.objects.first()
        assert loaded.period_minutes == 660
        assert loaded == pct

    def test_more_than_one(self) -> None:
        PeriodicallyCheckAccessTokens.objects.create(period_minutes=None)
        PeriodicallyCheckAccessTokens.objects.create(period_minutes=882)
        with pytest.raises(
            ToolchainAssertion,
            match="More than one PeriodicallyCheckAccessTokens detected. This is not supported currently.",
        ):
            PeriodicallyCheckAccessTokens.create_or_update(660)


@pytest.mark.django_db()
class TestPeriodicallyRevokeTokens:
    def test_create_new(self) -> None:
        assert PeriodicallyRevokeTokens.objects.count() == 0
        prt = PeriodicallyRevokeTokens.create_or_update(period_minutes=1921, max_tokens=150)
        assert PeriodicallyRevokeTokens.objects.count() == 1
        loaded = PeriodicallyRevokeTokens.objects.first()
        assert loaded.period_minutes == 1921
        assert loaded.max_tokens == 150
        assert loaded == prt

    def test_update_existing(self) -> None:
        assert PeriodicallyRevokeTokens.objects.count() == 0
        PeriodicallyRevokeTokens.create_or_update(period_minutes=81, max_tokens=34)
        assert PeriodicallyRevokeTokens.objects.count() == 1
        prt = PeriodicallyRevokeTokens.create_or_update(period_minutes=939, max_tokens=12)
        assert PeriodicallyRevokeTokens.objects.count() == 1
        loaded = PeriodicallyRevokeTokens.objects.first()
        assert loaded.period_minutes == 939
        assert loaded.max_tokens == 12
        assert loaded == prt

    def test_more_than_one(self) -> None:
        PeriodicallyRevokeTokens.objects.create(period_minutes=None, max_tokens=300)
        PeriodicallyRevokeTokens.objects.create(period_minutes=190, max_tokens=93)
        with pytest.raises(
            ToolchainAssertion,
            match="More than one PeriodicallyRevokeTokens detected. This is not supported currently.",
        ):
            PeriodicallyRevokeTokens.create_or_update(period_minutes=939, max_tokens=12)


@pytest.mark.django_db()
class TestRestrictedAccessToken:
    def test_allocate(self) -> None:
        assert RestrictedAccessToken.objects.count() == 0
        token_id = RestrictedAccessToken.allocate(key="tylerchicken", repo_id="bobcob")
        assert RestrictedAccessToken.objects.count() == 1
        token = RestrictedAccessToken.objects.first()
        assert token.id == token_id
        assert token.repo_id == "bobcob"
        assert token.ci_build_key == "tylerchicken"
        assert token.issued_at.timestamp() == pytest.approx(utcnow().timestamp())

    def test_tokens_for_key(self) -> None:
        assert RestrictedAccessToken.objects.count() == 0
        assert RestrictedAccessToken.tokens_for_key("tylerchicken") == 0
        RestrictedAccessToken.allocate(key="tylerchicken", repo_id="bobcob")
        assert RestrictedAccessToken.tokens_for_key("tylerchicken") == 1
        RestrictedAccessToken.allocate(key="tylerchicken", repo_id="bobcob")
        RestrictedAccessToken.allocate(key="tylerchicken", repo_id="bobcob")
        RestrictedAccessToken.allocate(key="tylerchicken", repo_id="bobcob")
        assert RestrictedAccessToken.tokens_for_key("tylerchicken") == 4


@pytest.mark.django_db()
class TestGithubRepoConfig:
    def test_for_repo(self) -> None:
        assert GithubRepoConfig.objects.count() == 0
        assert GithubRepoConfig.for_repo(repo_id="soup") is None
        GithubRepoConfig.objects.create(repo_id="soup", max_build_tokens=33, started_treshold_sec=90, token_ttl_sec=120)
        cfg = GithubRepoConfig.for_repo(repo_id="soup")
        assert cfg is not None

    def test_values(self) -> None:
        GithubRepoConfig.objects.create(
            repo_id="ovaltine", max_build_tokens=8, started_treshold_sec=33, token_ttl_sec=180
        )
        cfg = GithubRepoConfig.for_repo(repo_id="ovaltine")
        assert cfg is not None
        assert cfg.repo_id == "ovaltine"
        assert cfg.max_build_tokens == 8
        assert cfg.started_treshold == datetime.timedelta(seconds=33)
        assert cfg.token_ttl == datetime.timedelta(seconds=180)


@pytest.mark.django_db()
class TestAccessTokenExchangeCode:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        user = create_staff(username="elaine", email="elaine@jerrysplace.com")
        Customer.create(slug="jerry", name="Jerry Seinfeld Inc").add_user(user)
        return user

    @pytest.fixture()
    def repo(self, user: ToolchainUser) -> Repo:
        customer = user.customers.first()
        return Repo.create("funnyguy", customer=customer, name="Jerry Seinfeld is a funny guy")

    def _assert_single_code(self, user, repo) -> AccessTokenExchangeCode:
        assert AccessTokenExchangeCode.objects.count() == 1
        exchange_code = AccessTokenExchangeCode.objects.first()
        assert exchange_code.user_api_id == user.api_id
        assert exchange_code.repo_id == repo.id
        return exchange_code

    def test_create_for_user(self, user, repo) -> None:
        assert AccessTokenExchangeCode.objects.count() == 0
        token_code = AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
        assert isinstance(token_code, str)
        assert len(token_code) == 22
        assert re.fullmatch(r"[A-Za-z0-9]+", token_code) is not None
        exchange_code = self._assert_single_code(user, repo)
        assert exchange_code.code == token_code
        assert exchange_code.state == AccessTokenExchangeCode.State.AVAILABLE
        assert exchange_code.is_available is True

    def test_create_multiple_for_user(self, user, repo) -> None:
        assert AccessTokenExchangeCode.objects.count() == 0
        token_code_1 = AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
        exchange_code_1 = self._assert_single_code(user, repo)
        assert exchange_code_1.code == token_code_1
        assert exchange_code_1.state == AccessTokenExchangeCode.State.AVAILABLE
        assert exchange_code_1.is_available is True
        token_code_2 = AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
        assert AccessTokenExchangeCode.objects.count() == 2
        exchange_code_1 = AccessTokenExchangeCode.objects.get(code=token_code_1)
        assert exchange_code_1.code == token_code_1
        assert exchange_code_1.state == AccessTokenExchangeCode.State.OVERRIDDEN
        assert exchange_code_1.is_available is False

        exchange_code_2 = AccessTokenExchangeCode.objects.get(code=token_code_2)
        assert exchange_code_2.repo_id == repo.pk
        assert exchange_code_2.user_api_id == user.api_id
        assert exchange_code_2.code == token_code_2
        assert exchange_code_2.state == AccessTokenExchangeCode.State.AVAILABLE
        assert exchange_code_2.is_available is True

    def test_use_code(self, user, repo) -> None:
        assert AccessTokenExchangeCode.objects.count() == 0
        token_code = AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
        exchange_code = self._assert_single_code(user, repo)
        assert exchange_code.state == AccessTokenExchangeCode.State.AVAILABLE
        exchange_code_data = AccessTokenExchangeCode.use_code(code=token_code)
        assert exchange_code_data is not None
        assert exchange_code_data.user_api_id == user.api_id
        assert exchange_code_data.repo_id == repo.id
        assert exchange_code_data.description.startswith("AccessTokenExchangeCode(state=") is True

        exchange_code = self._assert_single_code(user, repo)
        assert exchange_code.state == AccessTokenExchangeCode.State.USED
        assert exchange_code.is_available is False

    def test_use_invalid_code(self, user, repo) -> None:
        assert AccessTokenExchangeCode.objects.count() == 0
        token_code = AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
        self._assert_single_code(user, repo)
        assert AccessTokenExchangeCode.use_code(code="soup") is None
        assert AccessTokenExchangeCode.use_code(code="") is None
        assert AccessTokenExchangeCode.use_code(code=token_code + "jerry") is None
        assert AccessTokenExchangeCode.use_code(code="upset" + token_code) is None

        exchange_code = self._assert_single_code(user, repo)
        assert exchange_code.state == AccessTokenExchangeCode.State.AVAILABLE
        assert exchange_code.is_available is True

    def test_expired_if_needed(self, user, repo) -> None:
        base_time = datetime.datetime(2019, 11, 22, 3, 45, 31, tzinfo=datetime.timezone.utc)
        with freeze_time(base_time):
            AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
            exchange_code = self._assert_single_code(user, repo)
            assert exchange_code.created_at == base_time
            assert exchange_code.state == AccessTokenExchangeCode.State.AVAILABLE
            assert exchange_code.expire_if_needed() is False

        with freeze_time(base_time + datetime.timedelta(minutes=2, seconds=1)):
            assert exchange_code.expire_if_needed() is True
            exchange_code = self._assert_single_code(user, repo)
            assert exchange_code.state == AccessTokenExchangeCode.State.EXPIRED
            assert exchange_code.is_available is False

    def test_use_expired_code(self, user, repo) -> None:
        base_time = datetime.datetime(2019, 11, 22, 3, 45, 31, tzinfo=datetime.timezone.utc)
        with freeze_time(base_time):
            token_code = AccessTokenExchangeCode.create_for_user(user, repo_id=repo.pk)
            exchange_code = self._assert_single_code(user, repo)
            assert exchange_code.created_at == base_time
            assert exchange_code.state == AccessTokenExchangeCode.State.AVAILABLE

        with freeze_time(base_time + datetime.timedelta(minutes=2, seconds=6)):
            assert AccessTokenExchangeCode.use_code(code=token_code) is None
            exchange_code = self._assert_single_code(user, repo)
            assert exchange_code.state == AccessTokenExchangeCode.State.EXPIRED
            assert exchange_code.is_available is False


@pytest.mark.django_db()
class TestUserCustomerAccessConfig:
    def test_create(self) -> None:
        assert UserCustomerAccessConfig.objects.count() == 0
        cfg = UserCustomerAccessConfig.create(
            customer_id="soup",
            user_api_id="rock-on",
            audience=AccessTokenAudience.FRONTEND_API | AccessTokenAudience.BUILDSENSE_API,
            is_org_admin=False,
        )
        assert UserCustomerAccessConfig.objects.count() == 1
        loaded = UserCustomerAccessConfig.objects.first()
        assert loaded == cfg
        assert loaded.user_api_id == cfg.user_api_id == "rock-on"
        assert loaded._allowed_audiences == cfg._allowed_audiences == "buildsense,frontend"
        assert loaded.role == UserCustomerAccessConfig.Role.USER
        assert loaded.is_admin is False
        assert (
            loaded.allowed_audiences
            == cfg.allowed_audiences
            == AccessTokenAudience.FRONTEND_API | AccessTokenAudience.BUILDSENSE_API
        )

    def test_update(self) -> None:
        cfg = UserCustomerAccessConfig.create(
            user_api_id="aqua-boy", customer_id="soup", audience=AccessTokenAudience.BUILDSENSE_API, is_org_admin=False
        )
        assert cfg._allowed_audiences == "buildsense"
        assert UserCustomerAccessConfig.objects.count() == 1
        cfg = UserCustomerAccessConfig.create(
            user_api_id="aqua-boy",
            customer_id="soup",
            audience=AccessTokenAudience.DEPENDENCY_API | AccessTokenAudience.BUILDSENSE_API,
            is_org_admin=False,
        )
        assert UserCustomerAccessConfig.objects.count() == 1
        loaded = UserCustomerAccessConfig.objects.first()
        assert loaded == cfg
        assert loaded.user_api_id == cfg.user_api_id == "aqua-boy"
        assert loaded.customer_id == cfg.customer_id == "soup"
        assert loaded.role == UserCustomerAccessConfig.Role.USER
        assert loaded.is_admin is False
        assert loaded._allowed_audiences == cfg._allowed_audiences == "buildsense,dependency"
        assert (
            loaded.allowed_audiences
            == cfg.allowed_audiences
            == AccessTokenAudience.DEPENDENCY_API | AccessTokenAudience.BUILDSENSE_API
        )

    def test_update_add_admin(self) -> None:
        created = UserCustomerAccessConfig.create_readwrite(
            user_api_id="aqua-boy", customer_id="soup", is_org_admin=OptionalBool.FALSE
        )
        assert created is True
        assert UserCustomerAccessConfig.objects.count() == 1
        cfg = UserCustomerAccessConfig.objects.first()
        assert cfg.allowed_audiences == (
            AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
        )
        assert cfg.role == UserCustomerAccessConfig.Role.USER
        assert cfg.is_admin is False
        assert UserCustomerAccessConfig.objects.count() == 1
        created = UserCustomerAccessConfig.create_readwrite(
            user_api_id="aqua-boy", customer_id="soup", is_org_admin=OptionalBool.TRUE
        )
        assert created is False
        assert UserCustomerAccessConfig.objects.count() == 1
        loaded = UserCustomerAccessConfig.objects.first()
        assert loaded.user_api_id == cfg.user_api_id == "aqua-boy"
        assert loaded.customer_id == cfg.customer_id == "soup"
        assert loaded.role == UserCustomerAccessConfig.Role.ORG_ADMIN
        assert loaded.is_admin is True
        assert loaded.allowed_audiences == (
            AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.IMPERSONATE
        )

    def test_update_revoke_admin(self) -> None:
        created = UserCustomerAccessConfig.create_readwrite(
            user_api_id="aqua-boy", customer_id="soup", is_org_admin=OptionalBool.TRUE
        )
        assert created is True
        assert UserCustomerAccessConfig.objects.count() == 1
        cfg = UserCustomerAccessConfig.objects.first()
        assert cfg.allowed_audiences == (
            AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.IMPERSONATE
        )
        assert cfg.role == UserCustomerAccessConfig.Role.ORG_ADMIN
        assert cfg.is_admin is True

        created = UserCustomerAccessConfig.create_readwrite(
            user_api_id="aqua-boy", customer_id="soup", is_org_admin=OptionalBool.FALSE
        )
        assert created is False
        assert UserCustomerAccessConfig.objects.count() == 1
        loaded = UserCustomerAccessConfig.objects.first()
        assert loaded.user_api_id == cfg.user_api_id == "aqua-boy"
        assert loaded.customer_id == cfg.customer_id == "soup"
        assert loaded.role == UserCustomerAccessConfig.Role.USER
        assert loaded.is_admin is False
        assert loaded.allowed_audiences == (
            AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
        )

    def test_get_audiences_for_user(self) -> None:
        UserCustomerAccessConfig.create(
            user_api_id="aqua-boy",
            customer_id="soup",
            audience=AccessTokenAudience.BUILDSENSE_API,
            is_org_admin=False,
        )
        UserCustomerAccessConfig.create(
            user_api_id="rock-on",
            customer_id="soup",
            audience=AccessTokenAudience.FRONTEND_API | AccessTokenAudience.BUILDSENSE_API,
            is_org_admin=False,
        )
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(customer_id="soup", user_api_id="jnt-optical")
            == AccessTokenAudience.FRONTEND_API
        )
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id="rock-on", customer_id="soup")
            == AccessTokenAudience.FRONTEND_API | AccessTokenAudience.BUILDSENSE_API
        )
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(customer_id="soup", user_api_id="aqua-boy")
            == AccessTokenAudience.BUILDSENSE_API
        )

    def test_get_role_for_user(self) -> None:
        assert (
            UserCustomerAccessConfig.get_role_for_user(customer_id="bob", user_api_id="joe")
            == UserCustomerAccessConfig.Role.USER
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="aqua-boy", customer_id="soup", is_org_admin=OptionalBool.TRUE
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="bagels", customer_id="soup", is_org_admin=OptionalBool.UNSET
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="bagels", customer_id="kramer", is_org_admin=OptionalBool.FALSE
        )

        assert (
            UserCustomerAccessConfig.get_role_for_user(customer_id="soup", user_api_id="bagels")
            == UserCustomerAccessConfig.Role.USER
        )
        assert (
            UserCustomerAccessConfig.get_role_for_user(customer_id="kramer", user_api_id="bagels")
            == UserCustomerAccessConfig.Role.USER
        )
        assert (
            UserCustomerAccessConfig.get_role_for_user(customer_id="soup", user_api_id="aqua-boy")
            == UserCustomerAccessConfig.Role.ORG_ADMIN
        )

    def test_get_role_map_for_user(self) -> None:
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="aqua-boy", customer_id="soup", is_org_admin=OptionalBool.UNSET
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="puddy", customer_id="costanza", is_org_admin=OptionalBool.TRUE
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="puddy", customer_id="soup", is_org_admin=OptionalBool.FALSE
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="puddy", customer_id="jerry", is_org_admin=OptionalBool.UNSET
        )
        UserCustomerAccessConfig.create_readwrite(
            user_api_id="puddy", customer_id="bagel", is_org_admin=OptionalBool.TRUE
        )
        UserCustomerAccessConfig.create_readwrite(user_api_id="bob", customer_id="soup", is_org_admin=OptionalBool.TRUE)
        assert UserCustomerAccessConfig.get_role_map_for_user(user_api_id="bob") == {
            "soup": UserCustomerAccessConfig.Role.ORG_ADMIN
        }
        assert UserCustomerAccessConfig.get_role_map_for_user(user_api_id="aqua-boy") == {
            "soup": UserCustomerAccessConfig.Role.USER
        }
        assert UserCustomerAccessConfig.get_role_map_for_user(user_api_id="puddy") == {
            "costanza": UserCustomerAccessConfig.Role.ORG_ADMIN,
            "soup": UserCustomerAccessConfig.Role.USER,
            "jerry": UserCustomerAccessConfig.Role.USER,
            "bagel": UserCustomerAccessConfig.Role.ORG_ADMIN,
        }

    def test_create_readwrite(self) -> None:
        assert UserCustomerAccessConfig.objects.count() == 0
        assert UserCustomerAccessConfig.create_readwrite(user_api_id="cosmo", customer_id="soup") is True
        assert UserCustomerAccessConfig.objects.count() == 1
        uac = UserCustomerAccessConfig.objects.first()
        assert (
            uac.allowed_audiences
            == AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
        )
        assert uac.user_api_id == "cosmo"
        assert uac.customer_id == "soup"
        assert uac.role == UserCustomerAccessConfig.Role.USER
        assert uac.is_admin is False

    def test_create_readwrite_admin(self) -> None:
        assert UserCustomerAccessConfig.objects.count() == 0
        assert (
            UserCustomerAccessConfig.create_readwrite(
                user_api_id="cosmo", customer_id="soup", is_org_admin=OptionalBool.TRUE
            )
            is True
        )
        assert UserCustomerAccessConfig.objects.count() == 1
        uac = UserCustomerAccessConfig.objects.first()
        assert (
            uac.allowed_audiences
            == AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.IMPERSONATE
        )
        assert uac.user_api_id == "cosmo"
        assert uac.customer_id == "soup"
        assert uac.role == UserCustomerAccessConfig.Role.ORG_ADMIN
        assert uac.is_admin is True

    def test_create_readwrite_no_op(self) -> None:
        UserCustomerAccessConfig.create(
            customer_id="soup",
            user_api_id="george",
            audience=AccessTokenAudience.FRONTEND_API,
            is_org_admin=False,
        )
        assert UserCustomerAccessConfig.objects.count() == 1
        assert UserCustomerAccessConfig.create_readwrite(customer_id="soup", user_api_id="george") is False
        assert UserCustomerAccessConfig.objects.count() == 1
        uac = UserCustomerAccessConfig.objects.first()
        assert uac.allowed_audiences == AccessTokenAudience.FRONTEND_API
        assert uac.user_api_id == "george"
        assert uac.customer_id == "soup"
        assert uac.role == UserCustomerAccessConfig.Role.USER
        assert uac.is_admin is False

    def test_set_admin(self) -> None:
        uac = UserCustomerAccessConfig.create(
            customer_id="soup",
            user_api_id="george",
            audience=AccessTokenAudience.FRONTEND_API,
            is_org_admin=False,
        )
        uac.set_admin(True)
        assert UserCustomerAccessConfig.objects.count() == 1
        assert UserCustomerAccessConfig.create_readwrite(customer_id="soup", user_api_id="george") is False
        assert UserCustomerAccessConfig.objects.count() == 1
        uac = UserCustomerAccessConfig.objects.first()
        assert uac.allowed_audiences == AccessTokenAudience.FRONTEND_API | AccessTokenAudience.IMPERSONATE
        assert uac.user_api_id == "george"
        assert uac.customer_id == "soup"
        assert uac.role == UserCustomerAccessConfig.Role.ORG_ADMIN
        assert uac.is_admin is True

    def _create_uac(self, customer: Customer, user: ToolchainUser, admin: bool):
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.FRONTEND_API,
            is_org_admin=admin,
        )

    def test_get_customer_admins(self, django_assert_num_queries) -> None:
        user = create_github_user(username="elaine", email="elaine@jerrysplace.com")
        admin_user_1 = create_github_user("cosmo", github_user_id="71123", github_username="kramer")
        admin_user_2 = create_github_user("david", github_user_id="8773", github_username="davidpuddy")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        self._create_uac(customer, user, admin=False)
        with django_assert_num_queries(1):
            assert UserCustomerAccessConfig.get_customer_admins(customer) == tuple()
        self._create_uac(customer, admin_user_1, admin=True)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.FRONTEND_API,
            is_org_admin=False,
        )
        with django_assert_num_queries(1):
            assert UserCustomerAccessConfig.get_customer_admins(customer) == (admin_user_1.api_id,)
        self._create_uac(customer, admin_user_2, admin=True)
        with django_assert_num_queries(1):
            assert set(UserCustomerAccessConfig.get_customer_admins(customer)) == {
                admin_user_1.api_id,
                admin_user_2.api_id,
            }
        admin_user_1.deactivate()
        with django_assert_num_queries(1):
            assert UserCustomerAccessConfig.get_customer_admins(customer) == (admin_user_2.api_id,)

        admin_user_2.deactivate()
        with django_assert_num_queries(1):
            assert UserCustomerAccessConfig.get_customer_admins(customer) == tuple()


@pytest.mark.django_db()
class TestUserAuth:
    def test_create(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        assert UserAuth.objects.count() == 0
        auth_user, created = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="455151551",
            username="emb",
            emails=["elaine@nbc.com", "elaine@benes.com"],
        )
        assert created is True
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.user_api_id == user.api_id
        assert user_auth.user_id == "455151551"
        assert user_auth.provider == AuthProvider.GITHUB
        assert user_auth.email_addresses == ("elaine@benes.com", "elaine@nbc.com")

    def test_get_social_user(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="455151551",
            username="emb",
            emails=["elaine@nbc.com", "elaine@benes.com"],
        )
        social_user = UserAuth.objects.first().get_social_user()
        assert social_user.uid == "455151551"
        assert social_user.provider == "github"

    def test_create_no_emails(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        assert UserAuth.objects.count() == 0
        auth_user, created = UserAuth.update_or_create(
            user=user, provider=AuthProvider.GITHUB, user_id="455151551", username="emb", emails=[]
        )
        assert created is True
        social_user = auth_user.get_social_user()
        assert social_user.provider == "github"
        assert social_user.uid == "455151551"
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.user_api_id == user.api_id
        assert user_auth.user_id == "455151551"
        assert user_auth.provider == AuthProvider.GITHUB
        assert user_auth.email_addresses == tuple()
        assert user_auth.username == "emb"

    def test_update(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        auth_user, created = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="emb",
            emails=["elaine@nbc.com", "elaine@benes.com"],
        )
        assert UserAuth.objects.count() == 1
        auth_user, created = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="emb",
            emails=["elaine@benes.com", "elaine@newyork.com"],
        )
        assert created is False
        social_user = auth_user.get_social_user()
        assert social_user.provider == "github"
        assert social_user.uid == "8887772"
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.user_api_id == user.api_id
        assert user_auth.user_id == "8887772"
        assert user_auth.provider == AuthProvider.GITHUB
        assert user_auth.email_addresses == ("elaine@benes.com", "elaine@newyork.com")
        assert user_auth.username == "emb"

    def test_update_no_emails(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        auth_user, created = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="emb",
            emails=["elaine@nbc.com", "elaine@benes.com"],
        )
        assert UserAuth.objects.count() == 1
        auth_user, created = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="marrie",
            emails=[],
        )
        assert created is False
        social_user = auth_user.get_social_user()
        assert social_user.provider == "github"
        assert social_user.uid == "8887772"
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.user_api_id == user.api_id
        assert user_auth.user_id == "8887772"
        assert user_auth.provider == AuthProvider.GITHUB
        assert user_auth.email_addresses == tuple()
        assert user_auth.username == "marrie"

    def test_create_multiple_providers(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        auth_user, created = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="emb",
            emails=["elaine@nbc.com", "elaine@benes.com"],
        )
        assert created is True
        social_user = auth_user.get_social_user()
        assert social_user.provider == "github"
        assert social_user.uid == "8887772"
        auth_user, created = UserAuth.update_or_create(
            user=user, provider=AuthProvider.BITBUCKET, user_id="22222", username="elainy", emails=["elaine@nbc.com"]
        )
        assert created is True
        social_user = auth_user.get_social_user()
        assert social_user.provider == "bitbucket"
        assert social_user.uid == "22222"
        assert UserAuth.objects.count() == 2
        github_auth = UserAuth.objects.get(user_id="8887772")
        bitbucket_auth = UserAuth.objects.get(user_id="22222")
        assert github_auth.user_api_id == user.api_id
        assert github_auth.provider == AuthProvider.GITHUB
        assert github_auth.user_id == "8887772"
        assert github_auth.email_addresses == ("elaine@benes.com", "elaine@nbc.com")
        assert github_auth.username == "emb"

        assert bitbucket_auth.user_api_id == user.api_id
        assert bitbucket_auth.provider == AuthProvider.BITBUCKET
        assert bitbucket_auth.user_id == "22222"
        assert bitbucket_auth.email_addresses == ("elaine@nbc.com",)
        assert bitbucket_auth.username == "elainy"

    def test_create_same_id_different_providers_different_users(self) -> None:
        user_1 = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        user_2 = ToolchainUser.create(username="george", email="george@jerrysplace.com")
        auth_user, created = UserAuth.update_or_create(
            user=user_1,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="emb",
            emails=["elaine@sony.com", "elaine@benes.com"],
        )
        assert created is True
        social_user = auth_user.get_social_user()
        assert social_user.provider == "github"
        assert social_user.uid == "8887772"
        auth_user, created = UserAuth.update_or_create(
            user=user_2,
            provider=AuthProvider.BITBUCKET,
            user_id="8887772",
            username="vandelay",
            emails=["george@costanza.com"],
        )
        assert created is True
        social_user = auth_user.get_social_user()
        assert social_user.provider == "bitbucket"
        assert social_user.uid == "8887772"
        assert UserAuth.objects.count() == 2
        user_1_auth = UserAuth.objects.get(user_api_id=user_1.api_id)
        user_2_auth = UserAuth.objects.get(user_api_id=user_2.api_id)
        assert user_1_auth.user_id == "8887772"
        assert user_1_auth.provider == AuthProvider.GITHUB
        assert user_1_auth.email_addresses == ("elaine@benes.com", "elaine@sony.com")
        assert user_1_auth.username == "emb"

        assert user_2_auth.user_id == "8887772"
        assert user_2_auth.provider == AuthProvider.BITBUCKET
        assert user_2_auth.email_addresses == ("george@costanza.com",)
        assert user_2_auth.username == "vandelay"

    def test_prevent_reuse_of_provider_user_id(self) -> None:
        user_1 = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        user_2 = ToolchainUser.create(username="benes", email="benese@jerrysplace.com")
        UserAuth.update_or_create(
            user=user_1, provider=AuthProvider.GITHUB, user_id="8887772", username="emb", emails=["elaine@sony.com"]
        )
        with pytest.raises(InvalidAuthUser, match="already exists and cannot be associated with"):
            UserAuth.update_or_create(
                user=user_2,
                provider=AuthProvider.GITHUB,
                user_id="8887772",
                username="marie",
                emails=["benese@nbc.com"],
            )

    def test_get_by_user_id(self) -> None:
        user_1 = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        user_2 = ToolchainUser.create(username="george", email="george@jerrysplace.com")
        UserAuth.update_or_create(
            user=user_1,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="marie",
            emails=["elaine@sony.com", "elaine@benes.com"],
        )
        UserAuth.update_or_create(
            user=user_2,
            provider=AuthProvider.BITBUCKET,
            user_id="6059303e630024006f000000",
            username="art",
            emails=["george@costanza.com"],
        )
        assert UserAuth.get_by_user_id(provider=AuthProvider.GITHUB, user_id="6059303e630024006f000000") is None
        user_auth = UserAuth.get_by_user_id(provider=AuthProvider.BITBUCKET, user_id="6059303e630024006f000000")
        assert user_auth is not None
        assert user_auth.user_api_id == user_2.api_id
        assert user_auth.provider == AuthProvider.BITBUCKET
        assert user_auth.user_id == "6059303e630024006f000000"

        user_auth = UserAuth.get_by_user_id(provider=AuthProvider.GITHUB, user_id="8887772")
        assert user_auth is not None
        assert user_auth.user_api_id == user_1.api_id
        assert UserAuth.get_by_user_id(provider=AuthProvider.BITBUCKET, user_id="8887772") is None

    @pytest.mark.parametrize(
        ("emails", "expected"),
        [
            (["elaine@nbc.com", "elaine@benes.com ", "elaine@benes.com", ""], "elaine@benes.com,elaine@nbc.com"),
            ([], ""),
            (["  ", " ", "", "\t\t\n", "\t", "\n"], ""),
            (["    elaine@nbc.com", "elaine@nbc.com\n", "elaine@nbc.com"], "elaine@nbc.com"),
            (["elaine@nyc.com\t", "    elaine@nbc.com", "elaine@nbc.com"], "elaine@nbc.com,elaine@nyc.com"),
        ],
    )
    def test_normalize_emails(self, emails: list[str], expected: str) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        UserAuth.update_or_create(user=user, provider=AuthProvider.GITHUB, user_id="32", username="emb", emails=emails)
        user_auth = UserAuth.objects.first()
        assert user_auth._email_addresses == expected

    @pytest.mark.parametrize("email", ["elai@ne@nbc.com", "elaine-benes.com ", "elaine@benes", "elaine@ benes.com"])
    def test_invalid_emails(self, email: str) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        fake = Faker()
        emails = [fake.unique.email() for _ in range(4)]
        emails.append(email)
        shuffle(emails)
        with pytest.raises(InvalidAuthUser, match="Invald email provided for user"):
            UserAuth.update_or_create(
                user=user, provider=AuthProvider.GITHUB, user_id="32", username="emb", emails=emails
            )
        assert UserAuth.objects.count() == 0

    def test_max_emails(self) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        fake = Faker()
        emails = [fake.unique.email() for _ in range(22)]
        with pytest.raises(ToolchainAssertion, match="Emails address count exceeds max allowed"):
            UserAuth.update_or_create(
                user=user, provider=AuthProvider.GITHUB, user_id="32", username="emb", emails=emails
            )
        assert UserAuth.objects.count() == 0

    def test_lookup_by_emails(self) -> None:
        user_1 = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        user_2 = ToolchainUser.create(username="george", email="george@jerrysplace.com")
        UserAuth.update_or_create(
            user=user_1,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="marrie",
            emails=["elaine@sony.com", "elaine@benes.com", "eb@seinfeld.com"],
        )
        UserAuth.update_or_create(
            user=user_2,
            provider=AuthProvider.GITHUB,
            user_id="6059303e630024006f000000",
            username="art",
            emails=["george@costanza.com", "george@nbc.com", "gc@seinfeld.com"],
        )
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "gc@seinfeld.com"}, exclude_provider=AuthProvider.BITBUCKET
        )
        assert user_api_ids == (user_2.api_id,)
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "gc@cbs.com"}, exclude_provider=AuthProvider.BITBUCKET
        )
        assert user_api_ids == (user_2.api_id,)
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@kramer.com", "gc@cbs.com"}, exclude_provider=AuthProvider.BITBUCKET
        )
        assert user_api_ids == tuple()
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "elaine@sony.com", "gc@cbs.com"}, exclude_provider=AuthProvider.BITBUCKET
        )
        assert set(user_api_ids) == {user_1.api_id, user_2.api_id}

    def test_lookup_by_emails_multiple_providers(self) -> None:
        user_1 = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        user_2 = ToolchainUser.create(username="george", email="george@jerrysplace.com")
        UserAuth.update_or_create(
            user=user_1,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="emb",
            emails=["elaine@sony.com", "elaine@benes.com", "eb@seinfeld.com"],
        )
        UserAuth.update_or_create(
            user=user_2,
            provider=AuthProvider.BITBUCKET,
            user_id="6059303e630024006f000000",
            username="art",
            emails=["george@costanza.com", "george@nbc.com", "gc@seinfeld.com"],
        )
        UserAuth.update_or_create(
            user=user_2,
            provider=AuthProvider.GITHUB,
            user_id="66633383883",
            username="art",
            emails=["gc@seinfeld.com"],
        )
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "george@costanza.com"}, exclude_provider=AuthProvider.BITBUCKET
        )
        assert user_api_ids == tuple()
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "gc@seinfeld.com"}, exclude_provider=AuthProvider.GITHUB
        )
        assert user_api_ids == (user_2.api_id,)
        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "gc@seinfeld.com"}, exclude_provider=AuthProvider.BITBUCKET
        )
        assert user_api_ids == (user_2.api_id,)

        user_api_ids = UserAuth.lookup_by_emails(
            emails={"george@nbc.com", "elaine@sony.com", "gc@cbs.com", "gc@seinfeld.com"},
            exclude_provider=AuthProvider.BITBUCKET,
        )
        assert set(user_api_ids) == {user_1.api_id, user_2.api_id}

    def test_lookup_by_emails_max_emails(self) -> None:
        fake = Faker()
        emails = {fake.unique.email() for _ in range(22)}
        with pytest.raises(ToolchainAssertion, match="Emails address count exceeds max allowed"):
            UserAuth.lookup_by_emails(emails, exclude_provider=AuthProvider.GITHUB)

    def test_get_emails_for_user(self) -> None:
        user_1 = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        user_2 = ToolchainUser.create(username="george", email="george@jerrysplace.com")
        UserAuth.update_or_create(
            user=user_1,
            provider=AuthProvider.GITHUB,
            user_id="8887772",
            username="marrie",
            emails=["elaine@sony.com", "elaine@benes.com", "eb@seinfeld.com"],
        )
        UserAuth.update_or_create(
            user=user_1,
            provider=AuthProvider.BITBUCKET,
            user_id="11111188888",
            username="emb",
            emails=["elaine@nbc.com", "emb@seinfeld.com", "elaine@benes.com"],
        )
        UserAuth.update_or_create(
            user=user_2,
            provider=AuthProvider.BITBUCKET,
            user_id="6059303e630024006f000000",
            username="art",
            emails=["george@costanza.com", "george@nbc.com", "gc@seinfeld.com"],
        )
        emails = UserAuth.get_emails_for_user(user_1.api_id)
        assert emails == {
            "elaine@nbc.com",
            "eb@seinfeld.com",
            "elaine@sony.com",
            "emb@seinfeld.com",
            "elaine@benes.com",
        }
        emails = UserAuth.get_emails_for_user(user_2.api_id)
        assert emails == {"george@nbc.com", "george@costanza.com", "gc@seinfeld.com"}


@pytest.mark.django_db()
class TestImpersonationSession:
    def test_cannot_start_session_twice(self):
        staff = create_staff(username="john", email="john.clarke@games.com.au", github_user_id="2000")
        user = create_github_user(
            username="wilson", email="wilson@deadbulder.com.au", github_user_id="94", github_username="wilson"
        )
        session = ImpersonationSession.objects.create(user_api_id=user.api_id, impersonator_api_id=staff.api_id)

        session.start()
        with pytest.raises(ToolchainAssertion):
            session.start()


@pytest.mark.django_db()
class TestPeriodicallyModels:
    @pytest.fixture(params=[PeriodicallyNotifyExpringTokens, PeriodicallyExportCustomers])
    def model_cls(self, request) -> type[WorkUnitPayload]:
        return request.param

    def test_create_new(self, model_cls) -> None:
        assert model_cls.objects.count() == 0
        pct = model_cls.create_or_update(88)
        assert model_cls.objects.count() == 1
        loaded = model_cls.objects.first()
        assert loaded.period_minutes == 88
        assert loaded == pct

    def test_update_existing(self, model_cls) -> None:
        assert model_cls.objects.count() == 0
        model_cls.create_or_update(88)
        assert model_cls.objects.count() == 1
        pct = model_cls.create_or_update(660)
        assert model_cls.objects.count() == 1
        loaded = model_cls.objects.first()
        assert loaded.period_minutes == 660
        assert loaded == pct

    def test_more_than_one(self, model_cls) -> None:
        model_cls.objects.create(period_minutes=None)
        model_cls.objects.create(period_minutes=882)
        with pytest.raises(
            ToolchainAssertion,
            match=f"More than one {model_cls.__name__} detected. This is not supported currently.",
        ):
            model_cls.create_or_update(660)


@pytest.mark.django_db()
class TestUserTermsOfServiceAcceptanceModels:
    def _accept_tos(self) -> None:
        UserTermsOfServiceAcceptance.accept_tos(
            user_api_id="jerry",
            tos_version="jerry-2022",
            client_ip="138.145.177.201",
            user_email="newman@jerry.com",
            request_id="no-soup-for-you",
        )

    def test_accept_new(self) -> None:
        assert UserTermsOfServiceAcceptance.objects.count() == 0
        self._accept_tos()
        assert UserTermsOfServiceAcceptance.objects.count() == 1
        tos = UserTermsOfServiceAcceptance.objects.first()
        assert tos.user_api_id == "jerry"
        assert tos.tos_version == "jerry-2022"
        assert tos.client_ip == "138.145.177.201"
        assert tos.email == "newman@jerry.com"
        assert tos.request_id == "no-soup-for-you"

    def test_accept_invalid_tos(self, django_assert_num_queries) -> None:
        assert UserTermsOfServiceAcceptance.objects.count() == 0
        with django_assert_num_queries(0), pytest.raises(ToolchainAssertion, match="TOS Version mismatch"):
            UserTermsOfServiceAcceptance.accept_tos(
                user_api_id="jerry",
                tos_version="kramer-2022",
                client_ip="999.2223.33888",
                user_email="newman@jerry.com",
                request_id="no-soup-for-you",
            )
        assert UserTermsOfServiceAcceptance.objects.count() == 0

    def test_accept_existing(self) -> None:
        self._accept_tos()
        UserTermsOfServiceAcceptance.accept_tos(
            user_api_id="jerry",
            tos_version="jerry-2022",
            client_ip="228.145.177.201",
            user_email="post@jerry.com",
            request_id="no-jerry",
        )
        assert UserTermsOfServiceAcceptance.objects.count() == 1
        tos = UserTermsOfServiceAcceptance.objects.first()
        assert tos.user_api_id == "jerry"
        assert tos.tos_version == "jerry-2022"
        assert tos.client_ip == "138.145.177.201"
        assert tos.email == "newman@jerry.com"
        assert tos.request_id == "no-soup-for-you"

    def test_has_accepted(self, django_assert_num_queries) -> None:
        UserTermsOfServiceAcceptance.objects.create(
            user_api_id="david",
            tos_version="jerry-2019",
            client_ip="228.145.177.201",
            email="post@jerry.com",
            request_id="no-jerry",
        )
        with django_assert_num_queries(1):
            assert UserTermsOfServiceAcceptance.has_accepted("jerry") is False
        self._accept_tos()
        with django_assert_num_queries(1):
            assert UserTermsOfServiceAcceptance.has_accepted("jerry") is True
        with django_assert_num_queries(1):
            assert UserTermsOfServiceAcceptance.has_accepted("david") is False


@pytest.mark.django_db()
class TestRemoteExecWorkerTokenModel:
    def test_create(self) -> None:
        assert RemoteExecWorkerToken.objects.count() == 0
        token = RemoteExecWorkerToken.create(
            customer_id="jerry",
            user_api_id="constanza",
            customer_slug="newman",
            description="Festivus for the rest of us",
        )
        assert RemoteExecWorkerToken.objects.count() == 1
        loaded = RemoteExecWorkerToken.objects.first()
        assert loaded.customer_id == token.customer_id == "jerry"
        assert loaded.user_api_id == token.user_api_id == "constanza"
        assert loaded.customer_slug == token.customer_slug == "newman"
        assert loaded.description == token.description == "Festivus for the rest of us"
        assert token.created_at.timestamp() == pytest.approx(utcnow().timestamp())
        assert token.created_at == loaded.created_at
        assert loaded.state == token.state == RemoteExecWorkerToken.State.ACTIVE
        assert loaded.token == token.token
        assert loaded.id == token.id

    def test_get_for_customer(self) -> None:
        token_1 = RemoteExecWorkerToken.create(
            customer_id="jerry", user_api_id="constanza", customer_slug="seinfeld", description="no soup for you"
        )
        token_2 = RemoteExecWorkerToken.create(
            customer_id="jerry",
            user_api_id="george",
            customer_slug="seinfeld",
            description="It's not a lie if you belive it",
        )
        token_3 = RemoteExecWorkerToken.create(
            customer_id="newman", user_api_id="constanza", customer_slug="usps", description="Have you seen the DMV?"
        )
        token_4 = RemoteExecWorkerToken.create(
            customer_id="newman", user_api_id="cosmo", customer_slug="usps", description="yo yo ma"
        )
        token_5 = RemoteExecWorkerToken.create(
            customer_id="kramer",
            user_api_id="cosmo",
            customer_slug="kramerica",
            description="Festivus for the rest of us",
        )
        assert RemoteExecWorkerToken.objects.count() == 5
        customer_1_tokens = RemoteExecWorkerToken.get_for_customer(customer_id="jerry")
        assert len(customer_1_tokens) == 2
        assert set(customer_1_tokens) == {token_1, token_2}
        customer_2_tokens = RemoteExecWorkerToken.get_for_customer(customer_id="newman")
        assert len(customer_2_tokens) == 2
        assert set(customer_2_tokens) == {token_3, token_4}
        assert RemoteExecWorkerToken.get_for_customer(customer_id="kramer") == (token_5,)

    def test_deactivate_or_404(self) -> None:
        token_id = RemoteExecWorkerToken.create(
            customer_id="jerry", user_api_id="constanza", customer_slug="seinfeld", description="no soup for you"
        ).id
        with pytest.raises(Http404):
            RemoteExecWorkerToken.deactivate_or_404(customer_id="jerry", token_id=f"{token_id}-bad")

        with pytest.raises(Http404):
            RemoteExecWorkerToken.deactivate_or_404(customer_id="seinfeld", token_id=token_id)

        token = RemoteExecWorkerToken.deactivate_or_404(customer_id="jerry", token_id=token_id)
        assert RemoteExecWorkerToken.objects.count() == 1
        loaded = RemoteExecWorkerToken.objects.first()
        assert loaded.state == token.state == RemoteExecWorkerToken.State.INACTIVE
        token = RemoteExecWorkerToken.deactivate_or_404(customer_id="jerry", token_id=token_id)
        loaded = RemoteExecWorkerToken.objects.first()
        assert loaded.state == token.state == RemoteExecWorkerToken.State.INACTIVE

    def test_deactivate(self) -> None:
        RemoteExecWorkerToken.create(
            customer_id="jerry", user_api_id="constanza", customer_slug="seinfeld", description="no soup for you"
        )
        assert RemoteExecWorkerToken.objects.count() == 1
        loaded = RemoteExecWorkerToken.objects.first()
        assert loaded.state == RemoteExecWorkerToken.State.ACTIVE
        assert loaded.deactivate() is True
        assert loaded.state == RemoteExecWorkerToken.State.INACTIVE
        loaded = RemoteExecWorkerToken.objects.first()
        assert loaded.state == RemoteExecWorkerToken.State.INACTIVE


@pytest.mark.django_db()
class TestPeriodicallyExportRemoteWorkerTokens:
    def test_create_new(self) -> None:
        assert PeriodicallyExportRemoteWorkerTokens.objects.count() == 0
        prt = PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=1921)
        assert PeriodicallyExportRemoteWorkerTokens.objects.count() == 1
        loaded = PeriodicallyExportRemoteWorkerTokens.objects.first()
        assert loaded.period_seconds == 1921
        assert loaded == prt

    def test_update_existing(self) -> None:
        assert PeriodicallyExportRemoteWorkerTokens.objects.count() == 0
        PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=81)
        assert PeriodicallyExportRemoteWorkerTokens.objects.count() == 1
        prt = PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=939)
        assert PeriodicallyExportRemoteWorkerTokens.objects.count() == 1
        loaded = PeriodicallyExportRemoteWorkerTokens.objects.first()
        assert loaded.period_seconds == 939
        assert loaded == prt

    def test_more_than_one(self) -> None:
        PeriodicallyExportRemoteWorkerTokens.objects.create(period_seconds=None)
        PeriodicallyExportRemoteWorkerTokens.objects.create(period_seconds=190)
        with pytest.raises(
            ToolchainAssertion,
            match="More than one PeriodicallyExportRemoteWorkerTokens detected. This is not supported currently.",
        ):
            PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=939)
