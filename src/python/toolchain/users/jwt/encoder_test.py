# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.users.jwt.encoder import JWTEncoder
from toolchain.users.jwt.keys import JWTSecretData, JWTSecretKey


class TestJWTEncoder:
    @pytest.fixture()
    def secret_data(self) -> JWTSecretData:
        return JWTSecretData(
            refresh_token_keys=(JWTSecretKey(key_id="cosmo", secret_key="when you control the mail"),),
            access_token_keys=(JWTSecretKey(key_id="newman", secret_key="you control information"),),
        )

    @pytest.fixture()
    def encoder(self, secret_data: JWTSecretData) -> JWTEncoder:
        return JWTEncoder(secret_data)

    def test_encode_ui_access_token(self, encoder: JWTEncoder) -> None:
        token_str = encoder.encode_access_token(
            expires_at=datetime.datetime(2030, 1, 1, 20, 10, 55, tzinfo=datetime.timezone.utc),
            issued_at=datetime.datetime(2021, 4, 27, tzinfo=datetime.timezone.utc),
            audience=AccessTokenAudience.FRONTEND_API,
            username="jerry",
            user_api_id="jambalaya",
            repo_id=None,
            customer_id=None,
            is_restricted=False,
            token_id="moles",
        )
        assert (
            token_str
            == "eyJhbGciOiJIUzI1NiIsImtpZCI6Im5ld21hbiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4OTM1Mjg2NTUsImlhdCI6MTYxOTQ4MTYwMCwiYXVkIjpbImZyb250ZW5kIl0sInVzZXJuYW1lIjoiamVycnkiLCJ0eXBlIjoiYWNjZXNzIiwidG9vbGNoYWluX3VzZXIiOiJqYW1iYWxheWEiLCJpc3MiOiJ0b29sY2hhaW4iLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6Mn0.OPU8g2vvqhZbt2HAPPdlVOxc3yTswndKGMbmRfy9mDk"
        )

    def test_encode_ui_refresh_token(self, encoder: JWTEncoder) -> None:
        token_str = encoder.encode_refresh_token(
            token_id="seinfeld",
            expires_at=datetime.datetime(2030, 10, 24, tzinfo=datetime.timezone.utc),
            issued_at=datetime.datetime(2021, 5, 2, tzinfo=datetime.timezone.utc),
            audience=AccessTokenAudience.FRONTEND_API,
            username="jerry",
            user_api_id="jambalaya",
        )
        assert (
            token_str
            == "eyJhbGciOiJIUzI1NiIsImtpZCI6ImNvc21vIiwidHlwIjoiSldUIn0.eyJleHAiOjE5MTkwMzA0MDAsImlhdCI6MTYxOTkxMzYwMCwiamlkIjoic2VpbmZlbGQiLCJhdWQiOlsiZnJvbnRlbmQiXSwidXNlcm5hbWUiOiJqZXJyeSIsInR5cGUiOiJyZWZyZXNoIiwidG9vbGNoYWluX3VzZXIiOiJqYW1iYWxheWEiLCJpc3MiOiJ0b29sY2hhaW4iLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6Mn0.gDSEpPZkV7x7JpBPwAM9XK70tPuwRy-pQXvs-5-vNzY"
        )

    def test_encode_api_refresh_token_bypass_not_allowed(self, encoder: JWTEncoder) -> None:
        expires_at = datetime.datetime(2030, 10, 24, tzinfo=datetime.timezone.utc)
        issued_at = datetime.datetime(2021, 5, 2, tzinfo=datetime.timezone.utc)
        with pytest.raises(ToolchainAssertion, match="Not allowed to add a bypass_db claim"):
            encoder.encode_refresh_token(
                token_id="seinfeld",
                expires_at=expires_at,
                issued_at=issued_at,
                audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW,
                username="kramer",
                user_api_id="jambalaya",
                repo_id="mole",
                customer_id="uncle-leo",
                bypass_db_check=True,
            )

    def test_encode_api_refresh_token_with_db_bypass(self, secret_data: JWTSecretData) -> None:
        encoder = JWTEncoder(secret_data, allow_bypass_db_claim=True)
        token_str = encoder.encode_refresh_token(
            token_id="seinfeld",
            expires_at=datetime.datetime(2030, 10, 24, tzinfo=datetime.timezone.utc),
            issued_at=datetime.datetime(2021, 5, 2, tzinfo=datetime.timezone.utc),
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW,
            username="jerry",
            user_api_id="jambalaya",
            repo_id="mole",
            customer_id="uncle-leo",
            bypass_db_check=True,
        )
        assert (
            token_str
            == "eyJhbGciOiJIUzI1NiIsImtpZCI6ImNvc21vIiwidHlwIjoiSldUIn0.eyJleHAiOjE5MTkwMzA0MDAsImlhdCI6MTYxOTkxMzYwMCwiamlkIjoic2VpbmZlbGQiLCJhdWQiOlsiYnVpbGRzZW5zZSIsImNhY2hlX3J3Il0sInVzZXJuYW1lIjoiamVycnkiLCJ0eXBlIjoicmVmcmVzaCIsInRvb2xjaGFpbl91c2VyIjoiamFtYmFsYXlhIiwidG9vbGNoYWluX3JlcG8iOiJtb2xlIiwidG9vbGNoYWluX2N1c3RvbWVyIjoidW5jbGUtbGVvIiwiYnlwYXNzX2RiIjp0cnVlLCJpc3MiOiJ0b29sY2hhaW4iLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6Mn0.Y5VAT4pwlqZfouTDOrusEcFwZAsqKx_bv9z62xk-QvQ"
        )

    def test_encode_api_refresh_token(self, encoder: JWTEncoder) -> None:
        token_str = encoder.encode_refresh_token(
            token_id="seinfeld",
            expires_at=datetime.datetime(2030, 10, 24, tzinfo=datetime.timezone.utc),
            issued_at=datetime.datetime(2021, 5, 2, tzinfo=datetime.timezone.utc),
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW,
            username="kramer",
            user_api_id="jambalaya",
            repo_id="mole",
            customer_id="uncle-leo",
        )
        assert (
            token_str
            == "eyJhbGciOiJIUzI1NiIsImtpZCI6ImNvc21vIiwidHlwIjoiSldUIn0.eyJleHAiOjE5MTkwMzA0MDAsImlhdCI6MTYxOTkxMzYwMCwiamlkIjoic2VpbmZlbGQiLCJhdWQiOlsiYnVpbGRzZW5zZSIsImNhY2hlX3J3Il0sInVzZXJuYW1lIjoia3JhbWVyIiwidHlwZSI6InJlZnJlc2giLCJ0b29sY2hhaW5fdXNlciI6ImphbWJhbGF5YSIsInRvb2xjaGFpbl9yZXBvIjoibW9sZSIsInRvb2xjaGFpbl9jdXN0b21lciI6InVuY2xlLWxlbyIsImlzcyI6InRvb2xjaGFpbiIsInRvb2xjaGFpbl9jbGFpbXNfdmVyIjoyfQ.Ey82vr_crz6hNWMff1Ew9Ba2pxq481cGgP2dh_FhnfU"
        )

    def test_encode_refresh_token_invalid(self, encoder: JWTEncoder) -> None:
        with pytest.raises(ToolchainAssertion, match="Must specify both repo & customer IDs"):
            encoder.encode_refresh_token(
                token_id="seinfeld",
                expires_at=datetime.datetime(2030, 10, 24, tzinfo=datetime.timezone.utc),
                issued_at=datetime.datetime(2021, 5, 2, tzinfo=datetime.timezone.utc),
                audience=AccessTokenAudience.FRONTEND_API,
                username="jerry",
                user_api_id="jambalaya",
                repo_id="nbc",
            )
        with pytest.raises(ToolchainAssertion, match="Must specify both repo & customer IDs"):
            encoder.encode_refresh_token(
                token_id="seinfeld",
                expires_at=datetime.datetime(2030, 10, 24, tzinfo=datetime.timezone.utc),
                issued_at=datetime.datetime(2021, 5, 2, tzinfo=datetime.timezone.utc),
                audience=AccessTokenAudience.FRONTEND_API,
                username="jerry",
                user_api_id="jambalaya",
                customer_id="sony",
            )
