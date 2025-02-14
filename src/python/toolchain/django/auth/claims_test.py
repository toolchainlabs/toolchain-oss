# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.claims import RepoClaims, UserClaims, load_claims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType


class TestRepoClaims:
    def test_invalid_claims(self) -> None:
        audience = AccessTokenAudience.for_pants_client()
        claims_dict = {
            "toolchain_claims_ver": 2,
            "type": "access",
            "toolchain_customer": "worlds-collide",
            "toolchain_repo": "independent-george",
            "toolchain_user": "lloyd-braun",
            "username": "kramer",
        }
        with pytest.raises(ToolchainAssertion, match="Invalid claims requested"):
            RepoClaims.create_repo_claims(claims_dict, audience, "cadillac")

    def test_as_json_dict(self) -> None:
        claims = RepoClaims(
            user_api_id="festivus",
            repo_pk="sweet_fancy_moses",
            customer_pk="cosmo",
            username="darren",
            token_type=AccessTokenType.ACCESS_TOKEN,
            audience=AccessTokenAudience.CACHE_RW | AccessTokenAudience.BUILDSENSE_API,
            token_id=None,
            impersonated_user_api_id="Kramerica",
            restricted=False,
        )
        assert claims.as_json_dict() == {
            "user_api_id": "festivus",
            "username": "darren",
            "audience": ["buildsense", "cache_rw"],
            "token_type": "access",
            "token_id": None,
            "customer_pk": "cosmo",
            "repo_pk": "sweet_fancy_moses",
            "restricted": False,
            "impersonated_user_api_id": "Kramerica",
        }

    def test_load_claims(self) -> None:
        claims = load_claims(
            {
                "user_api_id": "festivus",
                "username": "darren",
                "audience": ["buildsense", "cache_ro"],
                "token_type": "refresh",
                "token_id": None,
                "customer_pk": "cosmo",
                "repo_pk": "sweet_fancy_moses",
                "restricted": False,
                "impersonated_user_api_id": "Kramerica",
            }
        )
        assert isinstance(claims, RepoClaims)
        assert claims.audience == AccessTokenAudience.CACHE_RO | AccessTokenAudience.BUILDSENSE_API
        assert claims.token_type == AccessTokenType.REFRESH_TOKEN
        assert claims.username == "darren"
        assert claims.user_api_id == "festivus"
        assert claims.customer_pk == "cosmo"
        assert claims.repo_pk == "sweet_fancy_moses"
        assert claims.restricted is False
        assert claims.impersonated_user_api_id == "Kramerica"


class TestUserClaims:
    def test_as_json_dict(self) -> None:
        claims = UserClaims(
            user_api_id="newman",
            username="hello-newman",
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            impersonation_session_id="its_about_100_metres",
        )
        assert claims.as_json_dict() == {
            "user_api_id": "newman",
            "username": "hello-newman",
            "audience": ["frontend"],
            "token_type": "refresh",
            "token_id": "soup",
            "impersonation_session_id": "its_about_100_metres",
        }

    def test_load_claims(self) -> None:
        claims = load_claims(
            {
                "user_api_id": "soup",
                "username": "cosmo",
                # "token_id": "seinfeld",
                "audience": ["frontend"],
                "token_type": "access",
                "impersonation_session_id": "its_about_100_metres",
            }
        )
        assert isinstance(claims, UserClaims)
        assert claims.audience == AccessTokenAudience.FRONTEND_API
        assert claims.token_type == AccessTokenType.ACCESS_TOKEN
        assert claims.username == "cosmo"
        assert claims.user_api_id == "soup"
        assert claims.impersonation_session_id == "its_about_100_metres"
