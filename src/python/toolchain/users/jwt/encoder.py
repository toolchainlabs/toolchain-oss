# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from jose import jwt

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.claims import RepoClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.users.jwt.keys import JWTSecretData

_logger = logging.getLogger(__name__)


class JWTEncoder:
    def __init__(self, key_data: JWTSecretData, allow_bypass_db_claim: bool = False) -> None:
        self._key_data = key_data
        self._allow_bypass_db_claim = allow_bypass_db_claim

    def encode_access_token(
        self,
        *,
        expires_at: datetime.datetime,
        issued_at: datetime.datetime,
        audience: AccessTokenAudience,
        username: str,
        user_api_id: str,
        repo_id: str | None,
        customer_id: str | None,
        is_restricted: bool,
        token_id: str | None = None,
        impersonation_session_id: str | None = None,
    ) -> str:
        claims_dict = {
            "exp": int(expires_at.timestamp()),
            "iat": int(issued_at.timestamp()),
            "aud": audience.to_claim(),
            "username": username,
            "type": AccessTokenType.ACCESS_TOKEN.value,
            "toolchain_user": user_api_id,
        }
        if impersonation_session_id:
            claims_dict["toolchain_impersonation_session"] = impersonation_session_id

        if is_restricted:
            # TODO: check permissions, some permission shouldn't be given to restricted access tokens
            claims_dict.update(sub="restricted", jid=token_id)
        if audience != AccessTokenAudience.FRONTEND_API:
            if not repo_id or not customer_id:
                raise ToolchainAssertion("repo_id & customer_id expected w/ non frontend API tokens")
            claims_dict.update({"toolchain_repo": repo_id, "toolchain_customer": customer_id})

        return self._encode_jwt(claims_dict, AccessTokenType.ACCESS_TOKEN)

    def encode_refresh_token(
        self,
        *,
        token_id: str,
        expires_at: datetime.datetime,
        issued_at: datetime.datetime,
        audience: AccessTokenAudience,
        username: str,
        user_api_id: str,
        repo_id: str | None = None,
        customer_id: str | None = None,
        bypass_db_check: bool = False,
        impersonation_session_id: str | None = None,
    ) -> str:
        claims = {
            "exp": int(expires_at.timestamp()),
            "iat": int(issued_at.timestamp()),
            "jid": token_id,
            "aud": audience.to_claim(),
            "username": username,
            "type": AccessTokenType.REFRESH_TOKEN.value,
            "toolchain_user": user_api_id,
        }
        if impersonation_session_id:
            claims["toolchain_impersonation_session"] = impersonation_session_id
        if customer_id or repo_id:
            if not customer_id or not repo_id:
                raise ToolchainAssertion("Must specify both repo & customer IDs")
            claims.update(
                {
                    "toolchain_repo": repo_id,
                    "toolchain_customer": customer_id,
                }
            )
        if bypass_db_check:
            # for use w/ e2e tests only
            if not self._allow_bypass_db_claim:
                raise ToolchainAssertion("Not allowed to add a bypass_db claim.")
            claims["bypass_db"] = True

        return self._encode_jwt(claims, AccessTokenType.REFRESH_TOKEN)

    def _encode_jwt(self, claims: dict, token_type: AccessTokenType) -> str:
        key = self._key_data.get_current(token_type)
        # kid=key id, iss=issuer.
        claims.update(iss="toolchain", toolchain_claims_ver=RepoClaims.CLAIMS_VERSION)
        return jwt.encode(claims, key.secret_key, algorithm=key.algorithm, headers={"kid": key.key_id})
