# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from unittest.mock import MagicMock

import pytest

from toolchain.django.auth.claims import RepoClaims, UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.middleware import InternalServicesMiddleware
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user


@pytest.mark.django_db()
class TestInternalServicesMiddleware:
    @pytest.fixture()
    def middleware(self) -> InternalServicesMiddleware:
        return InternalServicesMiddleware(get_response=lambda request: None)

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(
            username="kramer", email="kramer@jerrysplace.com", full_name="Cosmo Kramer", github_user_id="8837733"
        )

    def test_not_app_view(self, middleware: InternalServicesMiddleware) -> None:
        req = MagicMock(headers={}, view_type="infra")
        middleware.process_request(req)
        assert not req.mock_calls

    def test_app_not_internal_call(self, middleware: InternalServicesMiddleware) -> None:
        req = MagicMock(headers={}, view_type="app")
        middleware.process_request(req)
        assert req.is_toolchain_internal_call is False
        assert req.internal_service_call_user is None
        assert req.user.is_authenticated is False

    def test_internal_call_no_user(self, middleware: InternalServicesMiddleware) -> None:
        req = MagicMock(headers={"X-Toolchain-Internal-Call": "1"}, view_type="app")
        middleware.process_request(req)
        assert req.is_toolchain_internal_call is True
        assert req.internal_service_call_user is None
        assert req.user.is_authenticated is False

    def test_internal_call_with_user(self, middleware: InternalServicesMiddleware, user: ToolchainUser) -> None:
        user_json = json.dumps({"user": {"api_id": user.api_id}})
        req = MagicMock(
            headers={"X-Toolchain-Internal-Call": "1", "X-Toolchain-Internal-Auth": user_json}, view_type="app"
        )
        middleware.process_request(req)
        assert req.is_toolchain_internal_call is True
        assert req.internal_service_call_user == user
        assert req.toolchain_claims is None
        assert req.user.is_authenticated is True

    def test_internal_call_with_user_and_user_claims(
        self, middleware: InternalServicesMiddleware, user: ToolchainUser
    ) -> None:
        internal_auth = json.dumps(
            {
                "user": {"api_id": user.api_id},
                "claims": {
                    "user_api_id": user.api_id,
                    "username": "cosmo",
                    "audience": ["frontend"],
                    "token_type": "access",
                },
            }
        )
        req = MagicMock(
            headers={"X-Toolchain-Internal-Call": "1", "X-Toolchain-Internal-Auth": internal_auth}, view_type="app"
        )
        middleware.process_request(req)
        assert req.is_toolchain_internal_call is True
        assert req.internal_service_call_user == user
        assert req.user.is_authenticated is True
        claims = req.toolchain_claims
        assert isinstance(claims, UserClaims)
        assert claims.audience == AccessTokenAudience.FRONTEND_API
        assert claims.token_type == AccessTokenType.ACCESS_TOKEN
        assert claims.user_api_id == user.api_id
        assert claims.username == "cosmo"

    def test_internal_call_with_user_and_repo_claims(
        self, middleware: InternalServicesMiddleware, user: ToolchainUser
    ) -> None:
        internal_auth = json.dumps(
            {
                "user": {"api_id": user.api_id},
                "claims": {
                    "user_api_id": user.api_id,
                    "username": "kramer",
                    "audience": ["buildsense", "cache_rw"],
                    "token_type": "access",
                    "token_id": None,
                    "customer_pk": "cosmo",
                    "repo_pk": "sweet_fancy_moses",
                    "restricted": False,
                    "impersonated_user_api_id": None,
                },
            }
        )
        req = MagicMock(
            headers={"X-Toolchain-Internal-Call": "1", "X-Toolchain-Internal-Auth": internal_auth}, view_type="app"
        )
        middleware.process_request(req)
        assert req.is_toolchain_internal_call is True
        assert req.internal_service_call_user == user
        assert req.user.is_authenticated is True
        claims = req.toolchain_claims
        assert isinstance(claims, RepoClaims)
        assert claims.audience == AccessTokenAudience.CACHE_RW | AccessTokenAudience.BUILDSENSE_API
        assert claims.token_type == AccessTokenType.ACCESS_TOKEN
        assert claims.username == "kramer"
        assert claims.user_api_id == user.api_id
        assert claims.customer_pk == "cosmo"
        assert claims.repo_pk == "sweet_fancy_moses"
        assert claims.restricted is False
        assert claims.impersonated_user_api_id is None
