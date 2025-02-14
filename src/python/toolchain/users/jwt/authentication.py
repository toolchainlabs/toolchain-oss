# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, ParseError

from toolchain.django.site.models import ToolchainUser
from toolchain.users.jwt.utils import InvalidAccessTokenError, check_access_token, check_refresh_token

_logger = logging.getLogger(__name__)


def _get_token_str(request) -> str | None:
    header = get_authorization_header(request)
    if not header:
        _logger.warning("unexpected_auth reason=no_auth_header")
        return None
    bearer, _, token_str = header.decode().partition(" ")
    if bearer != "Bearer" or not token_str:
        _logger.warning(f"Malformed authentication header ({header})")
        raise ParseError(f"Malformed authentication header ({header})")
    return token_str


class RefreshTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token_str = _get_token_str(request)
        if not token_str:
            return None
        try:
            claims = check_refresh_token(token_str)
        except InvalidAccessTokenError as error:
            _logger.warning(f"Invalid Refresh token {token_str} {error!r}", exc_info=True)
            # We want to special case JWT expiration to let the client gracefully handle it and show a proper error message.
            # In all other case, we shouldn't disclouse the failure reason in the response, just log it so we can troubleshoot.
            raise AuthenticationFailed("Invalid Refresh Token")
        user = ToolchainUser.get_by_api_id(claims.user_api_id)
        if not user:
            _logger.warning(f"No user for {claims.user_api_id} - {claims!r}")
            raise AuthenticationFailed("User N/A")
        # claims will be exposed to the app (views) via request.auth
        return user, claims


class AccessTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token_str = _get_token_str(request)
        if not token_str:
            return None
        impersonation_user_api_id = request.headers.get("X-Toolchain-Impersonate")
        try:
            claims = check_access_token(token_str, impersonation_user_api_id)
        except InvalidAccessTokenError as error:
            _logger.warning(f"Invalid Access token {token_str} {error!r}", exc_info=True)
            # We want to special case JWT expiration to let the client gracefully handle it and show a proper error message.
            # In all other case, we shouldn't disclouse the failure reason in the response, just log it so we can troubleshoot.
            raise AuthenticationFailed("Invalid Access Token")
        user = ToolchainUser.get_by_api_id(claims.user_api_id)
        if not user:
            _logger.warning(f"No user for {claims.user_api_id} - {claims!r}")
            raise AuthenticationFailed("User N/A")
        # claims will be exposed to the app (views) via request.auth
        _logger.info(f"auth_from_auth_token {user=}")
        return user, claims


class AuthenticationFromInternalHeaders(BaseAuthentication):
    """Reads attributes from the request set by InternalServicesMiddleware.

    This auth class is used in internal services and relies on auth done upstream (in service router by
    JwtAuthMiddleware)
    """

    def authenticate(self, request):
        if not hasattr(request, "is_toolchain_internal_call"):
            _logger.warning(f"is_toolchain_internal_call missing on {request.path=}")
            return None
        if not request.is_toolchain_internal_call:
            return None
        user = request.internal_service_call_user
        claims = request.toolchain_claims
        if not user or not claims:
            return None
        # claims will be exposed to the app (views) via request.auth
        return user, claims
