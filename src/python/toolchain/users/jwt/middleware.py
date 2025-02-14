# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from rest_framework.authentication import get_authorization_header

from toolchain.django.auth.claims import Claims
from toolchain.django.auth.constants import REFRESH_TOKEN_COOKIE_NAME, AccessTokenType
from toolchain.django.auth.impersonation import ImpersonationData
from toolchain.django.site.models import ToolchainUser
from toolchain.users.jwt.utils import InvalidAccessTokenError, check_access_token, check_refresh_token, get_token_type
from toolchain.users.models import ImpersonationAuditLog, ImpersonationSession

_logger = logging.getLogger(__name__)


def _get_user(request, claims: Claims) -> ToolchainUser | None:
    if not hasattr(request, "_cached_tc_user"):
        request._cached_tc_user = ToolchainUser.get_by_api_id(api_id=claims.user_api_id, include_inactive=False)
    return request._cached_tc_user


def _get_token_string(request) -> tuple[str | None, bool]:
    auth_header = get_authorization_header(request)
    if auth_header:
        bearer, _, token_str = auth_header.decode().partition(" ")
        if bearer != "Bearer" or not token_str:
            raise PermissionDenied()
        return token_str, True
    return request.COOKIES.get(REFRESH_TOKEN_COOKIE_NAME), False


def _safe_get_claims(token_str: str, from_header: bool, impersonation_user_api_id: str | None) -> Claims | None:
    try:
        return _get_claims(token_str, from_header, impersonation_user_api_id)
    except InvalidAccessTokenError as error:
        _logger.warning(f"failed to validate token {from_header=}: {error}")
        return None


def _get_claims(token_str: str, from_header: bool, impersonation_user_api_id: str | None) -> Claims:
    if from_header:
        token_type = get_token_type(token_str)
        if token_type == AccessTokenType.ACCESS_TOKEN:
            return check_access_token(token_str, impersonation_user_api_id=impersonation_user_api_id)
    return check_refresh_token(token_str)


class JwtAuthMiddleware(MiddlewareMixin):
    def process_request(self, request):
        token_str, from_header = _get_token_string(request)
        impersonation_user_api_id = request.headers.get("X-Toolchain-Impersonate")
        claims = _safe_get_claims(token_str, from_header, impersonation_user_api_id) if token_str else None
        request.toolchain_jwt_claims = claims

        user = _get_user(request, claims) if claims else None
        request.toolchain_impersonation = check_impersonation_session(request, user, claims) if user else None
        request.toolchain_user = user
        request.user = user or ToolchainUser.get_anonymous_user()
        request.customer_id = getattr(claims, "customer_pk", "unknown")


def check_impersonation_session(request, user: ToolchainUser, claims: Claims) -> ImpersonationData | None:
    """Raises `PermissionDenied` if the token claims an impersonation session, and it not belong to the user the token
    belongs to, or if the impersonation session has expired."""

    impersonation_session_id = getattr(
        claims, "impersonation_session_id", None
    )  # TODO: handle RepoClaims more elegantly

    if impersonation_session_id is None:
        return None

    session = ImpersonationSession.get_started_session_for_user_or_none(impersonation_session_id, user.api_id)

    if session is None:
        raise PermissionDenied("Impersonation session is invalid.")

    audit_log_data = {
        "headers": dict(request.headers),
    }
    if request.method == "GET":
        audit_log_data["GET"] = request.GET
    elif request.method == "POST":
        audit_log_data["POST"] = request.POST

    ImpersonationAuditLog.create(
        session=session, path=request.path, method=request.method, audit_log_data=audit_log_data
    )
    impersonator = ToolchainUser.get_by_api_id(session.impersonator_api_id)
    return ImpersonationData(user=user, impersonator=impersonator, expiry=session.expires_at)
