# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.test import RequestFactory
from jose import jwt

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.claims import UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_staff
from toolchain.users.jwt.middleware import JwtAuthMiddleware, check_impersonation_session
from toolchain.users.jwt.utils import get_or_create_refresh_token_for_ui
from toolchain.users.models import ImpersonationAuditLog, ImpersonationSession


def _generate_ui_access_token_header(user: ToolchainUser):
    return generate_access_token_header(user, AccessTokenAudience.FRONTEND_API)


def generate_access_token_header(user: ToolchainUser, audience: AccessTokenAudience, **extra) -> str:
    now = utcnow()
    key = settings.JWT_AUTH_KEY_DATA.get_current(AccessTokenType.ACCESS_TOKEN)
    claims_dict = {
        "exp": int((now + datetime.timedelta(minutes=1)).timestamp()),
        "iss": "toolchain",
        "toolchain_claims_ver": 2,
        "iat": int(now.timestamp()),
        "aud": audience.to_claim(),
        "username": user.username,
        "type": AccessTokenType.ACCESS_TOKEN.value,
        "toolchain_user": user.api_id,
        **extra,
    }
    token_str = jwt.encode(claims_dict, key.secret_key, algorithm="HS256", headers={"kid": key.key_id})
    return f"Bearer {token_str}"


def _create_fake_request(auth_header: str | None, data: dict | None = None, headers: dict | None = None) -> HttpRequest:
    all_headers = {"HTTP_AUTHORIZATION": auth_header} if auth_header else {}
    all_headers.update(headers or {})
    return RequestFactory().get("/festivus", data=(data or {}), **all_headers)


@pytest.mark.django_db()
class TestJwtAuthMiddleware:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")

    @pytest.fixture()
    def staff_member(self) -> ToolchainUser:
        user = create_staff(username="john", email="john.clarke@games.com.au")
        user.is_superuser = True
        user.save()
        return user

    @pytest.fixture()
    def middleware(self) -> JwtAuthMiddleware:
        return JwtAuthMiddleware(get_response=lambda request: None)

    def test_access_token_from_header(self, user: ToolchainUser, middleware: JwtAuthMiddleware) -> None:
        header = _generate_ui_access_token_header(user)
        request = _create_fake_request(auth_header=header)
        middleware.process_request(request)
        lazy_user = request.toolchain_user
        assert lazy_user.api_id == user.api_id
        assert request.toolchain_jwt_claims is not None
        assert request.toolchain_jwt_claims.is_access_token is True
        assert request.toolchain_jwt_claims.audience == AccessTokenAudience.FRONTEND_API

    def test_access_token_from_header_with_impersonation(
        self, rf: RequestFactory, user: ToolchainUser, middleware: JwtAuthMiddleware
    ) -> None:
        auth_header = generate_access_token_header(
            user,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
            toolchain_repo="ocean",
            toolchain_customer="shrimp",
        )
        request = rf.get("/festivus", HTTP_AUTHORIZATION=auth_header, HTTP_X_TOOLCHAIN_IMPERSONATE="jerk-store")
        middleware.process_request(request)
        lazy_user = request.toolchain_user
        assert lazy_user.api_id == user.api_id
        assert request.toolchain_jwt_claims is not None
        assert request.toolchain_jwt_claims.is_access_token is True
        assert (
            request.toolchain_jwt_claims.audience
            == AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE
        )
        assert request.toolchain_jwt_claims.impersonated_user_api_id == "jerk-store"
        assert request.toolchain_jwt_claims.repo_pk == "ocean"
        assert request.toolchain_jwt_claims.customer_pk == "shrimp"

    def test_access_token_from_header_with_impersonation_permissions_missing(
        self, rf: RequestFactory, user: ToolchainUser, middleware: JwtAuthMiddleware
    ) -> None:
        auth_header = generate_access_token_header(user, audience=AccessTokenAudience.BUILDSENSE_API)
        request = rf.get("/festivus", HTTP_AUTHORIZATION=auth_header, HTTP_X_TOOLCHAIN_IMPERSONATE="jerk-store")

        middleware.process_request(request)
        assert request.toolchain_user is None
        assert request.toolchain_jwt_claims is None

    def test_refresh_token_header(self, user: ToolchainUser, middleware: JwtAuthMiddleware) -> None:
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        request = _create_fake_request(auth_header=f"Bearer {token_str}")
        middleware.process_request(request)
        lazy_user = request.toolchain_user
        assert lazy_user.api_id == user.api_id
        assert request.toolchain_jwt_claims is not None
        assert request.toolchain_jwt_claims.is_access_token is False
        assert request.toolchain_jwt_claims.audience == AccessTokenAudience.FRONTEND_API

    def test_refresh_token_cookie(self, rf: RequestFactory, user: ToolchainUser, middleware: JwtAuthMiddleware) -> None:
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        rf.cookies["refreshToken"] = token_str
        request = rf.get("/mole")
        middleware.process_request(request)
        lazy_user = request.toolchain_user
        assert lazy_user.api_id == user.api_id
        assert request.toolchain_jwt_claims is not None
        assert request.toolchain_jwt_claims.is_access_token is False
        assert request.toolchain_jwt_claims.audience == AccessTokenAudience.FRONTEND_API

    def test_refresh_token_with_ui_impersonation(
        self, rf: RequestFactory, user: ToolchainUser, staff_member: ToolchainUser, middleware: JwtAuthMiddleware
    ) -> None:
        session = _create_started_impersonation_session(user, staff_member)
        token_str, _ = get_or_create_refresh_token_for_ui(user, impersonation_session_id=session.id)
        rf.cookies["refreshToken"] = token_str
        request = rf.get("/mole")
        middleware.process_request(request)
        lazy_user = request.toolchain_user
        assert lazy_user.api_id == user.api_id
        assert request.toolchain_jwt_claims is not None
        assert request.toolchain_jwt_claims.is_access_token is False
        assert request.toolchain_jwt_claims.audience == AccessTokenAudience.FRONTEND_API

    def test_token_with_ui_impersonation_expired(
        self, rf: RequestFactory, user: ToolchainUser, staff_member: ToolchainUser, middleware: JwtAuthMiddleware
    ) -> None:
        session = ImpersonationSession.objects.create(
            user_api_id=user.api_id,
            impersonator_api_id=staff_member.api_id,
            expires_at=utcnow() - datetime.timedelta(minutes=1),
            started=True,
        )

        token_str, _ = get_or_create_refresh_token_for_ui(user, impersonation_session_id=session.id)

        rf.cookies["refreshToken"] = token_str
        request = rf.get("/mole")
        with pytest.raises(PermissionDenied):
            middleware.process_request(request)


@pytest.mark.django_db()
class TestUIImpersonation:
    @pytest.fixture()
    def impersonator(self) -> ToolchainUser:
        user = create_staff(username="john", email="john.clarke@games.com.au")
        user.is_superuser = True
        user.save()
        return user

    @pytest.fixture()
    def impersonatee(self) -> ToolchainUser:
        user = ToolchainUser.create(username="wilson", email="wilson@deadbuilder.com.au")
        return user

    @pytest.fixture()
    def incorrect_user(self) -> ToolchainUser:
        user = ToolchainUser.create(username="frank", email="gdaygdaygday@countryvetcop.net.au")
        return user

    @pytest.fixture()
    def plausible_request(self) -> HttpRequest:
        return _create_fake_request(
            auth_header=None,
            headers={"length": "94 metres"},
            data={"location": "100_metres_track"},
        )

    @pytest.fixture()
    def session(self, impersonator: ToolchainUser, impersonatee: ToolchainUser) -> ImpersonationSession:
        return _create_started_impersonation_session(impersonatee, impersonator)

    @pytest.fixture()
    def claims(self, impersonatee: ToolchainUser, session: ImpersonationSession) -> UserClaims:
        return UserClaims(
            user_api_id=impersonatee.api_id,
            username=impersonatee.username,
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id=None,
            impersonation_session_id=session.id,
        )

    def test_ui_impersonation_with_valid_session(
        self, impersonatee: ToolchainUser, claims: UserClaims, plausible_request: HttpRequest
    ) -> None:
        assert ImpersonationAuditLog.objects.count() == 0

        # The impersonation session, given an ID for a valid session, should pass without exceptions
        session_data = check_impersonation_session(plausible_request, impersonatee, claims)
        assert session_data is not None
        assert session_data.user.api_id == claims.user_api_id == impersonatee.api_id

        # The impersonation session should add an audit log for this page view.
        log = ImpersonationAuditLog.objects.all()[0]
        assert "headers" in log.data
        assert plausible_request.method in log.data
        assert log.method == plausible_request.method
        assert log.path == plausible_request.path

    def test_ui_impersonation_with_expired_session(
        self,
        impersonatee: ToolchainUser,
        session: ImpersonationSession,
        claims: UserClaims,
        plausible_request: HttpRequest,
    ) -> None:
        session.expires_at = utcnow() - datetime.timedelta(minutes=10)
        session.save()
        with pytest.raises(PermissionDenied, match="Impersonation session is invalid."):
            check_impersonation_session(plausible_request, impersonatee, claims)

    def test_ui_impersonation_with_not_started_session(
        self,
        impersonatee: ToolchainUser,
        session: ImpersonationSession,
        claims: UserClaims,
        plausible_request: HttpRequest,
    ) -> None:
        session.started = False
        session.save()
        with pytest.raises(PermissionDenied, match="Impersonation session is invalid."):
            check_impersonation_session(plausible_request, impersonatee, claims)

    def test_ui_impersonation_with_session_for_incorrect_user(
        self, incorrect_user: ToolchainUser, session, claims: UserClaims, plausible_request: HttpRequest
    ) -> None:
        with pytest.raises(PermissionDenied, match="Impersonation session is invalid."):
            check_impersonation_session(plausible_request, incorrect_user, claims)


def _create_started_impersonation_session(
    impersonatee: ToolchainUser, impersonator: ToolchainUser
) -> ImpersonationSession:
    return ImpersonationSession.objects.create(
        user_api_id=impersonatee.api_id,
        impersonator_api_id=impersonator.api_id,
        started=True,
    )
