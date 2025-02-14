# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from freezegun import freeze_time
from jose import jwt

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.claims import RepoClaims, UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.site.models import (
    AccessTokenUsage,
    AllocatedRefreshToken,
    Customer,
    CustomerType,
    Repo,
    ToolchainUser,
)
from toolchain.users.jwt.encoder import JWTEncoder
from toolchain.users.jwt.keys import JWTSecretData, JWTSecretKey
from toolchain.users.jwt.utils import (
    AccessToken,
    InvalidAccessTokenError,
    InvalidTokenRequest,
    check_access_token,
    check_refresh_token,
    generate_access_token_from_refresh_token,
    generate_refresh_token,
    generate_restricted_access_token,
    get_or_create_refresh_token_for_ui,
)


def repo_claims_for_test(
    user: ToolchainUser | str,
    audience: AccessTokenAudience,
    token_type: AccessTokenType,
    restricted: bool = False,
    repo_slug: str = "newman",
    customer_slug: str = "seinfeld",
) -> RepoClaims:
    customer = Customer.create(slug=customer_slug, name="Seinfeld Dev Enterprises")
    repo = Repo.create(slug=repo_slug, customer=customer, name="Hello Newman")
    return RepoClaims(
        user_api_id=user if isinstance(user, str) else user.api_id,
        customer_pk=customer.id,
        repo_pk=repo.id,
        username="jerry_s",
        audience=audience,
        token_type=token_type,
        token_id="tinsel" if token_type == AccessTokenType.REFRESH_TOKEN else None,
        restricted=restricted,
    )


class Tokens:
    # This token expires on October 19th, 2025
    UI_REFRESH_TOKEN = (
        "ts:1588117601",
        "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODgxMTc2MDEiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjIwNzU1MjYwMDAsImlhdCI6MTU5MTY4NjAwMCwiamlkIjoiWmVrR2RUOGlIQnJnZGJidDhFS0sycCIsImF1ZCI6WyJmcm9udGVuZCJdLCJ1c2VybmFtZSI6ImNvc21vIiwidHlwZSI6InJlZnJlc2giLCJ0b29sY2hhaW5fdXNlciI6ImhLTW02aTlESEx3UTZrTUE5WFVzVWEiLCJpc3MiOiJ0b29sY2hhaW4iLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6Mn0.wJMvHm5nmFGbrU58kGEq9by_9rQkVjqHkp0dlqShseg",
    )

    # alg = 'none'
    BAD_TOKEN = "eyJhbGciOiBudWxsLCAidHlwIjogIkpXVCIsICJraWQiOiAiOTgifQ==.eyJ1c2VybmFtZSI6ICJzb3VwIiwgImppZCI6ICJmZXN0aXZ1cyIsICJpc3MiOiAiamVycnkifQ==."

    # Expires January 16th, 2028
    API_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODI4NDM3NDYiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE4MzE2MjI0MDAsImlhdCI6MTU5MTY4NjAwMCwiYXVkIjpbImJ1aWxkc2Vuc2UiXSwidXNlcm5hbWUiOiJqZXJyeV9zIiwidHlwZSI6ImFjY2VzcyIsInRvb2xjaGFpbl91c2VyIjoiamVycnkiLCJ0b29sY2hhaW5fcmVwbyI6InNlaW5mZWxkIiwidG9vbGNoYWluX2N1c3RvbWVyIjoibmJjIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9.xIpL2RhHs78PLT_3f6PFqyGLvwixNuCbUulk0f6j7bw"

    # Expires January 16th, 2028
    ACCESS_TOKEN_WITH_IMPERSONATION_REQUEST = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODI4NDM3NDYiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE4MzE2MjI0MDAsImlhdCI6MTU4MTkyNjQwMCwiYXVkIjpbImJ1aWxkc2Vuc2UiXSwidXNlcm5hbWUiOiJqZXJyeV9zIiwidHlwZSI6ImFjY2VzcyIsInRvb2xjaGFpbl91c2VyIjoiamVycnkiLCJ0b29sY2hhaW5fcmVwbyI6InNlaW5mZWxkIiwidG9vbGNoYWluX2N1c3RvbWVyIjoibmJjIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9.wcxt3taQt1i5B1B1cZSDn3tHmYAUy759-oZaV-w2JXM"

    # Expires on March 3rd, 2027.
    REFRESH_TOKEN_V2 = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODU3Nzg1MjIiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE4MDU5MTQyMzMsImlhdCI6MTYyMTIwOTYwMCwiamlkIjoiVzlSeDJYcDVXYlNkVk56dGlqN3F0dSIsImF1ZCI6WyJidWlsZHNlbnNlIl0sInVzZXJuYW1lIjoia3JhbWVyIiwidHlwZSI6InJlZnJlc2giLCJ0b29sY2hhaW5fdXNlciI6Ill1MkpvNmkzR2M5WHFjc05heTlGb1AiLCJ0b29sY2hhaW5fcmVwbyI6ImluZGVwZW5kZW50LWdlb3JnZSIsInRvb2xjaGFpbl9jdXN0b21lciI6Indvcmxkcy1jb2xsaWRlIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9.Nxdp4kRwHktGe06_u_4V6kbCjbq3PVZOtGf3AXUoaM0"

    # Expires on November 21, 2044.
    REFRESH_TOKEN_V2_WITH_IMPERSONATION = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODU3NzgzNzMiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjIzNjMzMzE4MzUsImlhdCI6MTYyMTEyMzIwMCwiamlkIjoiTEpaOFpLWkpna0Jja0hWRXk3RUtHdCIsImF1ZCI6WyJidWlsZHNlbnNlIiwiZGVwZW5kZW5jeSIsImltcGVyc29uYXRlIl0sInVzZXJuYW1lIjoiaXp6eSIsInR5cGUiOiJyZWZyZXNoIiwidG9vbGNoYWluX3VzZXIiOiJVQVpIbjhTY3lxeVdRM3ZNU0I3Z2M5IiwidG9vbGNoYWluX3JlcG8iOiJpbmRlcGVuZGVudC1nZW9yZ2UiLCJ0b29sY2hhaW5fY3VzdG9tZXIiOiJkZWwtYm9jYS12aXN0YSIsImlzcyI6InRvb2xjaGFpbiIsInRvb2xjaGFpbl9jbGFpbXNfdmVyIjoyfQ.h5qBw6V7l_EOjYMSCBMg9m04AYXCYMXjp_h9CHkuLE4"

    # Expires on August 23, 2027.
    REFRESH_TOKEN_V2_WITH_INTERNAL_TOOLCHAIN = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODU3Nzk2NzUiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3ODc0NTUwODMsImlhdCI6MTYyMDYwNDgwMCwiamlkIjoiYnBLTEVhUHJEd0djdktLTUtwQ0E1QiIsImF1ZCI6WyJidWlsZHNlbnNlIiwiZGVwZW5kZW5jeSIsImludGVybmFsX3Rvb2xjaGFpbiJdLCJ1c2VybmFtZSI6InNvdXAiLCJ0eXBlIjoicmVmcmVzaCIsInRvb2xjaGFpbl91c2VyIjoiZ240cGU1aE14ejY5WmNpa2FFa3J2RiIsInRvb2xjaGFpbl9yZXBvIjoiYXJtYW5pIiwidG9vbGNoYWluX2N1c3RvbWVyIjoib3ZhbHRpbmUiLCJpc3MiOiJ0b29sY2hhaW4iLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6Mn0.tSl60lfpA5kLRHUUI38rUv0tVBPgk6Y8Dj6_dLKdsFs"


@pytest.mark.django_db()
class TestRefreshTokens:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="festivus", name="Feats of strength")

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="cosmo", email="cosmo.kramer@jerry.com")

    def _create_user(self, user_api_id: str) -> ToolchainUser:
        return ToolchainUser.objects.create(username="kramer", email="kramer@jerry.com", api_id=user_api_id)

    def _create_objects_with_ids(self, user_api_id: str, customer_id: str, repo_id: str) -> ToolchainUser:
        user = self._create_user(user_api_id)
        customer = Customer.objects.create(name="Top of the muffin", slug="muffintop", id=customer_id)
        customer.add_user(user)
        Repo.objects.create(name="Pop the Top", slug="top", customer=customer, id=repo_id)
        return user

    @property
    def current_refresh_token_key_id(self) -> str:
        return settings.JWT_AUTH_KEY_DATA.get_current_refresh_token_key().key_id

    def test_generate_refresh_token(self, customer) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@jerry.com")
        now = utcnow()
        token_str = generate_refresh_token(
            user=user,
            repo_pk="independent-george",
            customer=customer,
            expiration_time=now + datetime.timedelta(minutes=10),
            audience=AccessTokenAudience.BUILDSENSE_API,
            description="You have the chicken, the hen, and the rooster",
        )
        assert isinstance(token_str, str)
        headers = jwt.get_unverified_header(token_str)
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": "rf:tinsel",
        }
        claims = jwt.decode(
            token_str, "refresh:it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False)
        )

        issued_at = claims.pop("iat")
        assert issued_at == pytest.approx(int(now.timestamp()))
        token = AllocatedRefreshToken.objects.get(id=claims["jid"])
        assert token is not None
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.description == "You have the chicken, the hen, and the rooster"
        assert int(token.issued_at.timestamp()) == issued_at
        assert token.expires_at == now + datetime.timedelta(minutes=10)
        assert claims == {
            "exp": int((now + datetime.timedelta(minutes=10)).timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense"],
            "jid": token.id,
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.id,
            "toolchain_repo": "independent-george",
            "toolchain_user": user.api_id,
            "username": "kramer",
        }

    def test_generate_refresh_token_with_impersonation(self, customer) -> None:
        user = ToolchainUser.create(username="izzy", email="izzy@mandelbaum.com")
        now = utcnow()
        token_str = generate_refresh_token(
            user=user,
            repo_pk="independent-george",
            customer=customer,
            expiration_time=now + datetime.timedelta(minutes=10),
            audience=AccessTokenAudience.for_pants_client(with_impersonation=True, internal_toolchain=False),
            description="You have the chicken, the hen, and the rooster",
        )
        assert isinstance(token_str, str)
        headers = jwt.get_unverified_header(token_str)
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": "rf:tinsel",
        }
        claims = jwt.decode(
            token_str, "refresh:it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False)
        )
        issued_at = claims.pop("iat")
        assert issued_at == pytest.approx(int(now.timestamp()))
        token = AllocatedRefreshToken.objects.get(id=claims["jid"])
        assert token is not None
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert int(token.issued_at.timestamp()) == issued_at
        assert token.description == "You have the chicken, the hen, and the rooster"

        assert token.expires_at == now + datetime.timedelta(minutes=10)
        assert claims == {
            "exp": int((now + datetime.timedelta(minutes=10)).timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw", "impersonate"],
            "jid": token.id,
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.id,
            "toolchain_repo": "independent-george",
            "toolchain_user": user.api_id,
            "username": "izzy",
        }

    def test_generate_refresh_token_with_internal_toolchain(self, customer) -> None:
        user = ToolchainUser.create(username="soup", email="kenny@mendis.com")
        now = utcnow()
        token_str = generate_refresh_token(
            user=user,
            repo_pk="armani",
            customer=customer,
            expiration_time=now + datetime.timedelta(minutes=10),
            audience=AccessTokenAudience.for_pants_client(with_impersonation=False, internal_toolchain=True),
            description="You have the chicken, the hen, and the rooster",
        )
        assert isinstance(token_str, str)
        headers = jwt.get_unverified_header(token_str)
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": "rf:tinsel",
        }
        claims = jwt.decode(
            token_str, "refresh:it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False)
        )
        issued_at = claims.pop("iat")
        assert issued_at == pytest.approx(int(now.timestamp()))
        token = AllocatedRefreshToken.objects.get(id=claims["jid"])
        assert token is not None
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.description == "You have the chicken, the hen, and the rooster"
        assert int(token.issued_at.timestamp()) == issued_at
        assert token.expires_at == now + datetime.timedelta(minutes=10)
        assert claims == {
            "exp": int((now + datetime.timedelta(minutes=10)).timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw", "internal_toolchain"],
            "jid": token.id,
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.id,
            "toolchain_repo": "armani",
            "toolchain_user": user.api_id,
            "username": "soup",
        }

    def test_max_allocated_refresh_tokens(self, customer: Customer) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@jerry.com")
        now = utcnow()
        token_ids = []
        for delta in range(0, AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API]):
            token_str = generate_refresh_token(
                user=user,
                repo_pk="independent-george",
                customer=customer,
                expiration_time=now + datetime.timedelta(minutes=3 + delta),
                audience=AccessTokenAudience.BUILDSENSE_API,
                description="You have the chicken, the hen, and the rooster",
            )
            token_ids.append(
                jwt.decode(
                    token_str, "refresh:it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False)
                )["jid"]
            )
        tokens_count = AllocatedRefreshToken.objects.count()
        assert (
            AllocatedRefreshToken.objects.filter(id__in=token_ids).count()
            == tokens_count
            == len(token_ids)
            == len(set(token_ids))
            == AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API]
            == 25
        )
        with pytest.raises(InvalidTokenRequest, match="Max number of active tokens reached") as error_info:
            generate_refresh_token(
                user=user,
                repo_pk="independent-george",
                customer=customer,
                expiration_time=now + datetime.timedelta(minutes=3 + delta),
                audience=AccessTokenAudience.BUILDSENSE_API,
                description="You have the chicken, the hen, and the rooster",
            )
        assert error_info.value.status_code == 401
        assert (
            AllocatedRefreshToken.objects.filter(id__in=token_ids).count()
            == tokens_count
            == len(token_ids)
            == len(set(token_ids))
            == 25
        )

    def test_check_refresh_token_repo(self, settings) -> None:
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1585778522")
        # Expires on March 3rd, 2027.
        token_str = Tokens.REFRESH_TOKEN_V2
        now = utcnow()
        self._create_objects_with_ids(
            user_api_id="Yu2Jo6i3Gc9XqcsNay9FoP", customer_id="worlds-collide", repo_id="independent-george"
        )
        AllocatedRefreshToken.objects.create(
            id="W9Rx2Xp5WbSdVNztij7qtu",
            user_api_id="Yu2Jo6i3Gc9XqcsNay9FoP",
            issued_at=now,
            expires_at=now + datetime.timedelta(days=300),
            _usage=AllocatedRefreshToken.Usage.API.value,
        )
        claims = check_refresh_token(token_str)
        assert isinstance(claims, RepoClaims)
        assert claims.user_api_id == "Yu2Jo6i3Gc9XqcsNay9FoP"
        assert claims.repo_pk == "independent-george"
        assert claims.customer_pk == "worlds-collide"
        assert claims.audience == AccessTokenAudience.BUILDSENSE_API
        assert claims.token_type == AccessTokenType.REFRESH_TOKEN
        assert claims.is_access_token is False
        assert claims.token_id == "W9Rx2Xp5WbSdVNztij7qtu"
        assert claims.can_impersonate is False

    def test_check_refresh_token_with_impersonation(self) -> None:
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1585778373")
        # This token expires on November 21, 2044.
        token_str = Tokens.REFRESH_TOKEN_V2_WITH_IMPERSONATION
        now = utcnow()
        self._create_objects_with_ids(
            user_api_id="UAZHn8ScyqyWQ3vMSB7gc9", customer_id="del-boca-vista", repo_id="independent-george"
        )
        AllocatedRefreshToken.objects.create(
            id="LJZ8ZKZJgkBckHVEy7EKGt",
            user_api_id="UAZHn8ScyqyWQ3vMSB7gc9",
            issued_at=now,
            expires_at=now + datetime.timedelta(days=300),
            _usage=AllocatedRefreshToken.Usage.API.value,
        )
        claims = check_refresh_token(token_str)
        assert isinstance(claims, RepoClaims)
        assert claims.user_api_id == "UAZHn8ScyqyWQ3vMSB7gc9"
        assert claims.repo_pk == "independent-george"
        assert claims.customer_pk == "del-boca-vista"
        assert (
            claims.audience
            == AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.DEPENDENCY_API | AccessTokenAudience.IMPERSONATE
        )
        assert claims.has_audience(AccessTokenAudience.BUILDSENSE_API) is True
        assert claims.has_audience(AccessTokenAudience.IMPERSONATE) is True
        assert claims.has_audience(AccessTokenAudience.INTERNAL_TOOLCHAIN) is False
        assert claims.has_audience(AccessTokenAudience.CACHE_RW) is False
        assert claims.has_audience(AccessTokenAudience.CACHE_RO) is False
        assert claims.has_audience(AccessTokenAudience.FRONTEND_API) is False
        assert claims.token_type == AccessTokenType.REFRESH_TOKEN
        assert claims.is_access_token is False
        assert claims.token_id == "LJZ8ZKZJgkBckHVEy7EKGt"
        assert claims.can_impersonate is True

    def test_check_refresh_token_with_internal_toolchain(self) -> None:
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1585779675")
        # This token expires on August 23, 2027.
        token_str = Tokens.REFRESH_TOKEN_V2_WITH_INTERNAL_TOOLCHAIN
        now = utcnow()
        self._create_objects_with_ids(user_api_id="gn4pe5hMxz69ZcikaEkrvF", customer_id="ovaltine", repo_id="armani")
        AllocatedRefreshToken.objects.create(
            id="bpKLEaPrDwGcvKKMKpCA5B",
            user_api_id="gn4pe5hMxz69ZcikaEkrvF",
            issued_at=now,
            expires_at=now + datetime.timedelta(days=300),
            _usage=AllocatedRefreshToken.Usage.API.value,
        )
        claims = check_refresh_token(token_str)
        assert isinstance(claims, RepoClaims)
        assert claims.user_api_id == "gn4pe5hMxz69ZcikaEkrvF"
        assert claims.repo_pk == "armani"
        assert claims.customer_pk == "ovaltine"
        assert (
            claims.audience
            == AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.DEPENDENCY_API
            | AccessTokenAudience.INTERNAL_TOOLCHAIN
        )
        assert claims.has_audience(AccessTokenAudience.BUILDSENSE_API) is True
        assert claims.has_audience(AccessTokenAudience.IMPERSONATE) is False
        assert claims.has_audience(AccessTokenAudience.INTERNAL_TOOLCHAIN) is True
        assert claims.has_audience(AccessTokenAudience.CACHE_RW) is False
        assert claims.has_audience(AccessTokenAudience.CACHE_RO) is False
        assert claims.has_audience(AccessTokenAudience.FRONTEND_API) is False
        assert claims.token_type == AccessTokenType.REFRESH_TOKEN
        assert claims.is_access_token is False
        assert claims.token_id == "bpKLEaPrDwGcvKKMKpCA5B"
        assert claims.can_impersonate is False

    def test_check_refresh_token_repo_unknown(self) -> None:
        # This token expires on August 25, 2033.
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1576617360")
        token_str = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1NzY2MTczNjAiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjIwMDg1NjYwMDAsImlhdCI6MTYwOTMxNTIwMCwiamlkIjoiV2FzY0tEQVA2SGthRUE2ZHRncTU0WSIsImF1ZCI6WyJidWlsZHNlbnNlIl0sInVzZXJuYW1lIjoia3JhbWVyIiwidHlwZSI6InJlZnJlc2giLCJ0b29sY2hhaW5fdXNlciI6IlY0Wnk3UlM2cFFzTFlXcFNOTXFCNUUiLCJ0b29sY2hhaW5fcmVwbyI6ImluZGVwZW5kZW50LWdlb3JnZSIsInRvb2xjaGFpbl9jdXN0b21lciI6Indvcmxkcy1jb2xsaWRlIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9.Y9CxwK1chV4ZhKDne5iroeGHxuZtSueZjYV924Jgv5I"
        with pytest.raises(
            InvalidAccessTokenError, match="Unknown API token with id=WascKDAP6HkaEA6dtgq54Y"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "unknown_token_id"

    @pytest.mark.parametrize(
        "bad_token",
        [
            "superman",
            "eyJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MSwiaXNzIjoidG9vbGNoYWluIiwiaWF0IjoxNTc0NzI3OTAwLCJ1c2VybmFtZSI6ImtyYW1lciIsInRvb2xjaGFpbl91c2VyIjoiVHFxd2FtS2pyUWRRNUhETHdpSGV6QyIsInRvb2xjaGFpbl9yZXBvIjoiaW5kZXBlbmRlbnQtZ2VvcmdlIiwidG9vbGNoYWluX2N1c3RvbWVyIjoid29ybGRzLWNvbGxpZGUifQ",
        ],
    )
    def test_refresh_token_failure(self, bad_token):
        with pytest.raises(InvalidAccessTokenError, match="Error decoding token headers"):
            check_refresh_token(bad_token)

    def test_check_refresh_token_repo_invalid_type(self) -> None:
        # This token expires on January 15, 2028.
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1582759976")
        token_str = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODI3NTk5NzYiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE4MzE1MzYwMDAsImlhdCI6MTU5MTY4NjAwMCwiYXVkIjpbImJ1aWxkc2Vuc2UiXSwidXNlcm5hbWUiOiJqZXJyeSIsInR5cGUiOiJhY2Nlc3MiLCJ0b29sY2hhaW5fdXNlciI6IlY0Wnk3UlM2cFFzTFlXcFNOTXFCNUUiLCJ0b29sY2hhaW5fcmVwbyI6InNlaW5mZWxkIiwidG9vbGNoYWluX2N1c3RvbWVyIjoibmJjIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9.8kLhWbBAvYruG2X08_-BjgL6vVlgLkrYokIWH_4AXEU"
        with pytest.raises(InvalidAccessTokenError, match="Invalid token type."):
            check_refresh_token(token_str)

    def test_check_refresh_token_no_signature(self) -> None:
        # alg = 'none'
        bad_token = Tokens.BAD_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "98")
        with pytest.raises(InvalidAccessTokenError, match="No algorithm was specified in the JWS header."):
            check_refresh_token(bad_token)

    def test_expired_refresh_token(
        self,
    ) -> None:
        now = utcnow()
        expiration = now - datetime.timedelta(minutes=10)
        with freeze_time(now - datetime.timedelta(minutes=40)):
            user = self._create_objects_with_ids(
                user_api_id="gn4pe5hMxz69ZcikaEkrvF", customer_id="worlds-collide", repo_id="independent-george"
            )
            token_str = generate_refresh_token(
                user=user,
                repo_pk="independent-george",
                customer=Customer.objects.get(id="worlds-collide"),
                expiration_time=expiration,
                audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
                description="You have the chicken, the hen, and the rooster",
            )
            assert check_refresh_token(token_str) is not None
        with pytest.raises(InvalidAccessTokenError, match="Signature has expired"):
            check_refresh_token(token_str)

    def test_invalid(self, customer: Customer) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@jerry.com")
        now = utcnow()
        with pytest.raises(ToolchainAssertion, match="Must specify audience"):
            generate_refresh_token(
                user=user,
                repo_pk="sue-allen",
                customer=customer,
                expiration_time=now + datetime.timedelta(minutes=10),
                audience=None,  # type: ignore
                description="You have the chicken, the hen, and the rooster",
            )

    def test_check_refresh_token_invalid_repo(self) -> None:
        now = utcnow()
        expiration = now + datetime.timedelta(minutes=10)
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        user = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1.add_user(user)
        customer_2.add_user(user)
        repo = Repo.create("cookie", customer_2, "Look to the cookie")

        # User associated with both customers, but repo is not associated with customer_1
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer_1,
            expiration_time=expiration,
            audience=AccessTokenAudience.for_pants_client(),
            description="You have the chicken, the hen, and the rooster",
        )
        with pytest.raises(InvalidAccessTokenError, match="Unknown API token with id=") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "repo_mismatch"

        # non-existent repo
        token_str = generate_refresh_token(
            user=user,
            repo_pk="tinsel",
            customer=customer_1,
            expiration_time=expiration,
            audience=AccessTokenAudience.for_pants_client(),
            description="You have the chicken, the hen, and the rooster",
        )
        with pytest.raises(InvalidAccessTokenError, match="Unknown API token with id=") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "repo_mismatch"

    def test_check_refresh_token_invalid_customer(self) -> None:
        now = utcnow()
        expiration = now + datetime.timedelta(minutes=10)
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("cookie", customer_1, "Look to the cookie")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        user = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_2.add_user(user)

        # User not associated with customer 1
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer_1,
            expiration_time=expiration,
            audience=AccessTokenAudience.for_pants_client(),
            description="You have the chicken, the hen, and the rooster",
        )
        with pytest.raises(InvalidAccessTokenError, match="Unknown API token with id=") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "customer_mismatch"

        # non-existent customer
        customer_1.add_user(user)
        assert check_refresh_token(token_str) is not None

        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=MagicMock(pk="bob", slug="sacamano"),
            expiration_time=expiration,
            audience=AccessTokenAudience.for_pants_client(),
            description="You have the chicken, the hen, and the rooster",
        )
        with pytest.raises(InvalidAccessTokenError, match="Unknown API token with id=") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "repo_mismatch"

    def test_get_or_create_refresh_token_for_ui_create(self, user: ToolchainUser) -> None:
        assert AllocatedRefreshToken.objects.count() == 0
        now = utcnow()
        token_str, expiration = get_or_create_refresh_token_for_ui(user)
        assert token_str is not None
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert expiration == token.expires_at
        headers = jwt.get_unverified_header(token_str)
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": self.current_refresh_token_key_id,
        }
        claims = jwt.decode(token_str, "it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False))
        expires_at = claims.pop("exp")
        issued_at = claims.pop("iat")
        assert (
            expires_at
            == int(token.expires_at.timestamp())
            == issued_at + int(datetime.timedelta(days=10).total_seconds())
        )
        assert issued_at == int(token.issued_at.timestamp()) == pytest.approx(now.timestamp())
        assert claims == {
            "jid": token.id,
            "aud": ["frontend"],
            "username": "cosmo",
            "type": "refresh",
            "toolchain_user": user.api_id,
            "iss": "toolchain",
            "toolchain_claims_ver": 2,
        }

    def test_get_or_create_refresh_token_for_ui_existing(self, user: ToolchainUser) -> None:
        assert AllocatedRefreshToken.objects.count() == 0
        token_str_1, expiration = get_or_create_refresh_token_for_ui(user)
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert token_str_1 is not None
        assert expiration == token.expires_at
        token_str_2, expiration = get_or_create_refresh_token_for_ui(user)
        assert AllocatedRefreshToken.objects.count() == 1
        assert token_str_2 == token_str_1
        headers = jwt.get_unverified_header(token_str_2)
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": self.current_refresh_token_key_id,
        }
        claims = jwt.decode(token_str_2, "it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False))
        del claims["iat"]
        exp = claims.pop("exp")
        assert exp == int(expiration.timestamp())
        assert claims == {
            "jid": token.id,
            "aud": ["frontend"],
            "username": "cosmo",
            "type": "refresh",
            "toolchain_user": user.api_id,
            "iss": "toolchain",
            "toolchain_claims_ver": 2,
        }

    def test_get_or_create_refresh_token_for_ui_existing_about_to_expire(self, user: ToolchainUser) -> None:
        now = utcnow()
        issued_time = now - datetime.timedelta(days=9, hours=23, minutes=55)
        with freeze_time(issued_time):
            token_str_1, expiration = get_or_create_refresh_token_for_ui(user)
        claims_1 = jwt.decode(token_str_1, "it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False))
        assert AllocatedRefreshToken.objects.count() == 1
        token_1 = AllocatedRefreshToken.objects.get(id=claims_1["jid"])
        assert token_1.expires_at == expiration
        token_str_2, expiration = get_or_create_refresh_token_for_ui(user)
        assert token_str_1 != token_str_2
        claims_2 = jwt.decode(token_str_2, "it's not you, its me", algorithms=["HS256"], options=dict(verify_aud=False))
        token_2 = AllocatedRefreshToken.objects.get(id=claims_2["jid"])
        assert expiration == token_2.expires_at
        assert token_1 != token_2

    def test_check_refresh_token_ui(self, user: ToolchainUser) -> None:
        key_id, token_str = Tokens.UI_REFRESH_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", key_id)
        now = utcnow()
        self._create_user(user_api_id="hKMm6i9DHLwQ6kMA9XUsUa")
        AllocatedRefreshToken.objects.create(
            id="ZekGdT8iHBrgdbbt8EKK2p",
            user_api_id="hKMm6i9DHLwQ6kMA9XUsUa",
            issued_at=now,
            expires_at=now + datetime.timedelta(days=300),
            _usage=AllocatedRefreshToken.Usage.UI.value,
        )
        claims = check_refresh_token(token_str)
        assert isinstance(claims, UserClaims)
        assert claims.user_api_id == "hKMm6i9DHLwQ6kMA9XUsUa"
        assert claims.audience == AccessTokenAudience.FRONTEND_API
        assert claims.token_type == AccessTokenType.REFRESH_TOKEN
        assert claims.is_access_token is False
        assert claims.token_id == "ZekGdT8iHBrgdbbt8EKK2p"

    def test_check_refresh_token_ui_inactive_user(self, user: ToolchainUser) -> None:
        key_id, token_str = Tokens.UI_REFRESH_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", key_id)
        now = utcnow()
        user = self._create_user(user_api_id="hKMm6i9DHLwQ6kMA9XUsUa")

        AllocatedRefreshToken.objects.create(
            id="ZekGdT8iHBrgdbbt8EKK2p",
            user_api_id="hKMm6i9DHLwQ6kMA9XUsUa",
            issued_at=now,
            expires_at=now + datetime.timedelta(days=300),
            _usage=AllocatedRefreshToken.Usage.UI.value,
        )
        user.deactivate()
        with pytest.raises(
            InvalidAccessTokenError, match="Unknown UI token with id=ZekGdT8iHBrgdbbt8EKK2p"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_user"

    def test_check_refresh_token_ui_unknown_token(self, user: ToolchainUser) -> None:
        key_id, token_str = Tokens.UI_REFRESH_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", key_id)
        user.deactivate()
        with pytest.raises(
            InvalidAccessTokenError, match="Unknown UI token with id=ZekGdT8iHBrgdbbt8EKK2p"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "unknown_token_id"

    def test_check_refresh_token_ui_revoked_token(self, user: ToolchainUser) -> None:
        key_id, token_str = Tokens.UI_REFRESH_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", key_id)
        now = utcnow()
        self._create_user(user_api_id="hKMm6i9DHLwQ6kMA9XUsUa")

        token = AllocatedRefreshToken.objects.create(
            id="ZekGdT8iHBrgdbbt8EKK2p",
            user_api_id="hKMm6i9DHLwQ6kMA9XUsUa",
            issued_at=now,
            expires_at=now + datetime.timedelta(days=300),
            _usage=AllocatedRefreshToken.Usage.UI.value,
        )
        token.revoke()
        with pytest.raises(
            InvalidAccessTokenError, match="Unknown UI token with id=ZekGdT8iHBrgdbbt8EKK2p"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "inactive_token"

    def _encode_db_bypass_token(
        self, repo: Repo | None, user: ToolchainUser, secret_data: JWTSecretData, expire_minutes: int = 10
    ) -> str:
        encoder = JWTEncoder(secret_data, allow_bypass_db_claim=True)
        now = utcnow()
        audience = (
            AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW
            if repo
            else AccessTokenAudience.FRONTEND_API
        )
        return encoder.encode_refresh_token(
            token_id="seinfeld",
            expires_at=now + datetime.timedelta(minutes=expire_minutes),
            issued_at=now,
            audience=audience,
            username=user.username,
            user_api_id=user.api_id,
            repo_id=repo.id if repo else None,
            customer_id=repo.customer_id if repo else None,
            bypass_db_check=True,
        )

    def test_refresh_token_with_db_bypass(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        customer.add_user(user)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        token_str = self._encode_db_bypass_token(repo, user, secret_data)

        claims = check_refresh_token(token_str)
        assert isinstance(claims, RepoClaims)
        assert claims.token_id == "seinfeld"
        assert claims.repo_pk == repo.id
        assert claims.customer_pk == customer.id
        assert claims.username == "cosmo"
        assert claims.user_api_id == user.api_id
        assert claims.is_access_token is False
        assert claims.audience == AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW

    def test_refresh_token_deny_db_bypass_user_not_associated(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        token_str = self._encode_db_bypass_token(repo, user, secret_data)
        with pytest.raises(
            InvalidAccessTokenError, match=f"Not allowed to bypass db check for customer {customer.id}"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass_customer"
        assert error_info.value.token_type == "refresh"

    def test_refresh_token_deny_db_bypass_customer_inactive(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        customer.add_user(user)
        token_str = self._encode_db_bypass_token(repo, user, secret_data)
        customer.deactivate()
        with pytest.raises(
            InvalidAccessTokenError, match=f"Not allowed to bypass db check for customer {customer.id}"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass_customer"
        assert error_info.value.token_type == "refresh"

    def test_refresh_token_deny_db_bypass_ttl_too_long(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        customer.add_user(user)
        token_str = self._encode_db_bypass_token(repo, user, secret_data, expire_minutes=60)
        with pytest.raises(InvalidAccessTokenError, match="Invalid expiration ") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass_expiration"
        assert error_info.value.token_type == "refresh"

    @pytest.mark.parametrize("customer_type", [CustomerType.OPEN_SOURCE, CustomerType.CUSTOMER, CustomerType.PROSPECT])
    def test_refresh_token_deny_db_bypass_invalid_customer_type(
        self, user: ToolchainUser, settings, customer_type: CustomerType
    ) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        token_str = self._encode_db_bypass_token(repo, user, secret_data)
        with pytest.raises(
            InvalidAccessTokenError, match=f"Not allowed to bypass db check for customer {customer.id}"
        ) as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass_customer"
        assert error_info.value.token_type == "refresh"

    def test_refresh_token_deny_db_bypass_inactive_user(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        customer.add_user(user)
        token_str = self._encode_db_bypass_token(repo, user, secret_data)
        user.deactivate()
        with pytest.raises(InvalidAccessTokenError, match="Invalid/inactive user specified") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass_user"
        assert error_info.value.token_type == "refresh"

    def test_refresh_token_deny_db_bypass_username_mismatch(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        customer = Customer.create(slug="nbc", name="Newman", customer_type=Customer.Type.INTERNAL)
        repo = Repo.create(slug="mail", customer=customer, name="usps mail")
        customer.add_user(user)
        token_str = self._encode_db_bypass_token(repo, user, secret_data)
        user.username = "kramer"
        user.save()
        with pytest.raises(InvalidAccessTokenError, match="Invalid/inactive user specified") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass_user"
        assert error_info.value.token_type == "refresh"

    def test_refresh_token_deny_db_bypass_user_claims(self, user: ToolchainUser, settings) -> None:
        secret_data = JWTSecretData.create_for_tests("mandelbaum-mandelbaum")
        settings.JWT_AUTH_KEY_DATA = secret_data
        token_str = self._encode_db_bypass_token(repo=None, user=user, secret_data=secret_data)
        with pytest.raises(InvalidAccessTokenError, match="Not allowed to bypass db check") as error_info:
            check_refresh_token(token_str)
        assert error_info.value.reason == "invalid_bypass"
        assert error_info.value.token_type == "refresh"


@pytest.mark.django_db()
class TestAccessTokens:
    @property
    def current_access_token_key(self) -> JWTSecretKey:
        return settings.JWT_AUTH_KEY_DATA.get_current_access_token_key()

    def test_generate_api_access_token_failures(self) -> None:
        bad_claims = repo_claims_for_test(
            "jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.ACCESS_TOKEN, customer_slug="bob"
        )
        with pytest.raises(ToolchainAssertion, match="Must provide a refresh token."):
            generate_access_token_from_refresh_token(bad_claims, datetime.timedelta(seconds=90))

        claims = repo_claims_for_test(
            "jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.REFRESH_TOKEN, customer_slug="puddy"
        )
        with pytest.raises(ToolchainAssertion, match="Invalid expiration_delta."):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=-90))
        with pytest.raises(ToolchainAssertion, match="Invalid expiration_delta."):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=1))
        with pytest.raises(ToolchainAssertion, match="Invalid expiration_delta."):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=10))

    def test_generate_api_access_token(self, django_assert_num_queries) -> None:
        now = utcnow()
        claims = repo_claims_for_test(
            "jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.REFRESH_TOKEN, customer_slug="frank"
        )
        repo = Repo.objects.get(id=claims.repo_pk)
        with django_assert_num_queries(1):
            access_token, extra_data = generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))
        assert extra_data == {"repo_id": repo.id, "customer_id": repo.customer_id}
        assert isinstance(access_token, AccessToken)
        assert isinstance(access_token.token, str)
        assert access_token.expiration.timestamp() == pytest.approx(
            (now + datetime.timedelta(seconds=180)).timestamp(), rel=2
        )
        headers = jwt.get_unverified_header(access_token.token)
        key = self.current_access_token_key
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": key.key_id,
        }
        claims_dict = jwt.decode(
            access_token.token, key.secret_key, algorithms=["HS256"], options=dict(verify_aud=False)
        )

        assert claims_dict.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims_dict.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims_dict == {
            "iss": "toolchain",
            "aud": ["buildsense"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_customer": repo.customer_id,
            "toolchain_repo": repo.id,
            "toolchain_user": "jerry",
            "username": "jerry_s",
        }

    def test_generate_access_token_with_impersonation(self, django_assert_num_queries) -> None:
        now = utcnow()
        claims = repo_claims_for_test(
            "jerry",
            AccessTokenAudience.for_pants_client(with_impersonation=True, internal_toolchain=False),
            AccessTokenType.REFRESH_TOKEN,
        )
        repo = Repo.objects.get(id=claims.repo_pk)
        with django_assert_num_queries(1):
            access_token, extra_data = generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))
        assert extra_data == {"repo_id": repo.id, "customer_id": repo.customer_id}
        assert isinstance(access_token, AccessToken)
        assert isinstance(access_token.token, str)
        expected_expiration = now + datetime.timedelta(seconds=180)
        assert access_token.expiration.timestamp() == pytest.approx(expected_expiration.timestamp(), 3)
        headers = jwt.get_unverified_header(access_token.token)
        key = self.current_access_token_key
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": key.key_id,
        }
        claims_dict = jwt.decode(
            access_token.token, key.secret_key, algorithms=["HS256"], options=dict(verify_aud=False)
        )

        assert claims_dict.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims_dict.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims_dict == {
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw", "impersonate"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_customer": repo.customer_id,
            "toolchain_repo": repo.id,
            "toolchain_user": "jerry",
            "username": "jerry_s",
        }

    def test_check_access_token_no_signature(self) -> None:
        # alg = 'none'
        bad_token = Tokens.BAD_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "98")
        with pytest.raises(InvalidAccessTokenError, match="No algorithm was specified in the JWS header."):
            check_access_token(bad_token)

    def test_check_api_access_token(self, settings) -> None:
        # Expires January 16th, 2028
        token_str = Tokens.API_ACCESS_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1582843746")
        claims = check_access_token(token_str)
        assert isinstance(claims, RepoClaims)
        assert claims.customer_pk == "nbc"
        assert claims.repo_pk == "seinfeld"
        assert claims.user_api_id == "jerry"
        assert claims.username == "jerry_s"
        assert claims.audience == AccessTokenAudience.BUILDSENSE_API
        assert claims.token_type == AccessTokenType.ACCESS_TOKEN
        assert claims.is_access_token is True
        assert claims.token_id is None

    def test_check_api_access_token_missing_key_id(self, settings) -> None:
        token_str = Tokens.API_ACCESS_TOKEN
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:999999999")
        with pytest.raises(InvalidAccessTokenError, match="Failed to decode token key_id=ts:1582843746"):
            check_access_token(token_str)

    @pytest.mark.parametrize(
        "bad_token",
        [
            "pirate",
            "eyJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MSwiaXNzIjoidG9vbGNoYWluIiwiaWF0IjoxNTc0NzI3OTAwLCJ1c2VybmFtZSI6ImtyYW1lciIsInRvb2xjaGFpbl91c2VyIjoiVHFxd2FtS2pyUWRRNUhETHdpSGV6QyIsInRvb2xjaGFpbl9yZXBvIjoiaW5kZXBlbmRlbnQtZ2VvcmdlIiwidG9vbGNoYWluX2N1c3RvbWVyIjoid29ybGRzLWNvbGxpZGUifQ",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MzE2NzU3NDcsImlzcyI6InRvb2xjaGFpbiIsImlhdCI6MTU4Mjg0Mzc0NywiYXVkIjpbImJ1aWxkc2Vuc2UiXSwidXNlcm5hbWUiOiJqZXJyeV9zIiwidHlwZSI6ImFjY2VzcyIsInRvb2xjaGFpbl9jbGFpbXNfdmVyIjoyLCJ0b29sY2hhaW5fdXNlciI6ImplcnJ5IiwidG9vbGNoYWluX3JlcG8iOiJzZWluZmVsZCIsInRvb2xjaGFpbl9jdXN0b21lciI6Im5iYyIsImtpZCI6InRzOjE1ODI4s",
            # "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.XXXXXX.C0V7rDpV2-D1xoFb2Dx4c8aJMUq4f4HiIRuZYnCRILs",
        ],
    )
    def test_check_access_token_failure(self, bad_token):
        with pytest.raises(InvalidAccessTokenError, match="Error decoding token headers"):
            check_access_token(bad_token)

    @pytest.mark.parametrize(
        "bad_token",
        [
            "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODI4NDM3NDYiLCJ0eXAiOiJKV1QifQ.XXXXXXX.xIpL2RhHs78PLT_3f6PFqyGLvwixNuCbUulk0f6j7bw"
        ],
    )
    def test_check_access_token_invalid_signature_failure(self, bad_token: str) -> None:
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1582843746")
        with pytest.raises(InvalidAccessTokenError, match="Signature verification failed"):
            check_access_token(bad_token)

    def test_invalid_api_token_type(self) -> None:
        customer = Customer.create(slug="festivus", name="Feats of strength")
        user = ToolchainUser.create(username="kramer", email="kramer@jerry.com")
        now = utcnow()
        refresh_token = generate_refresh_token(
            user=user,
            repo_pk="independent-george",
            customer=customer,
            expiration_time=now + datetime.timedelta(minutes=10),
            audience=AccessTokenAudience.BUILDSENSE_API,
            description="You have the chicken, the hen, and the rooster",
        )
        with pytest.raises(InvalidAccessTokenError, match="Invalid token type"):
            check_access_token(refresh_token)

    def test_check_api_access_token_expired(self, django_assert_num_queries) -> None:
        now = utcnow()
        claims = repo_claims_for_test("jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.REFRESH_TOKEN)

        with freeze_time(now - datetime.timedelta(minutes=40)), django_assert_num_queries(1):
            access_token, _ = generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))
        with pytest.raises(InvalidAccessTokenError, match="Signature has expired"):
            check_access_token(access_token.token)

    def test_check_api_access_token_with_impersonation_denied(self, settings, django_assert_num_queries) -> None:
        # Expires January 16th, 2028
        token_str = Tokens.ACCESS_TOKEN_WITH_IMPERSONATION_REQUEST
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1582843746")
        with pytest.raises(InvalidAccessTokenError, match="Impersonation request denied"), django_assert_num_queries(0):
            check_access_token(token_str, impersonation_user_api_id="magic-pan")

    def test_generate_ui_access_token(self, django_assert_num_queries) -> None:
        now = utcnow()
        claims = UserClaims(
            user_api_id="newman",
            username="hello_newman",
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
        )
        with django_assert_num_queries(0):
            access_token, extra_data = generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))
        assert extra_data is None
        assert isinstance(access_token, AccessToken)
        assert isinstance(access_token.token, str)
        assert access_token.expiration == pytest.approx((now + datetime.timedelta(seconds=180)).replace(microsecond=0))
        headers = jwt.get_unverified_header(access_token.token)
        key = self.current_access_token_key
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": key.key_id,
        }
        claims_dict = jwt.decode(
            access_token.token, key.secret_key, algorithms=["HS256"], options=dict(verify_aud=False)
        )
        assert claims_dict.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims_dict.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims_dict == {
            "iss": "toolchain",
            "aud": ["frontend"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_user": "newman",
            "username": "hello_newman",
        }

    def test_generate_ui_access_token_failures(self) -> None:
        bad_claims = UserClaims(
            user_api_id="newman",
            username="hello-newman",
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.ACCESS_TOKEN,
            token_id=None,
        )
        with pytest.raises(ToolchainAssertion, match="Must provide a refresh token."):
            generate_access_token_from_refresh_token(bad_claims, datetime.timedelta(seconds=90))

        claims = UserClaims(
            user_api_id="newman",
            username="hello-newman",
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
        )
        with pytest.raises(ToolchainAssertion, match="Invalid expiration_delta."):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=-90))
        with pytest.raises(ToolchainAssertion, match="Invalid expiration_delta."):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=1))
        with pytest.raises(ToolchainAssertion, match="Invalid expiration_delta."):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=10))

    def test_check_ui_access_token(self) -> None:
        # Expires July 19th, 2028
        settings.JWT_AUTH_KEY_DATA = JWTSecretData.create_for_tests_identical("it's not you, its me", "ts:1588380864")
        token_str = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1ODgzODA4NjQiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE4NDc2MDI4MDAsImlhdCI6MTYwMzc4MjAwMCwiYXVkIjpbImZyb250ZW5kIl0sInVzZXJuYW1lIjoiaGVsbG9fbmV3bWFuIiwidHlwZSI6ImFjY2VzcyIsInRvb2xjaGFpbl91c2VyIjoibmV3bWFuIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9.Enij7db2_LBDn4-kv8sQuufveWNBE7-K1xW_0f4J_ao"
        claims = check_access_token(token_str)
        assert isinstance(claims, UserClaims)
        assert claims.user_api_id == "newman"
        assert claims.username == "hello_newman"
        assert claims.audience == AccessTokenAudience.FRONTEND_API
        assert claims.token_type == AccessTokenType.ACCESS_TOKEN
        assert claims.is_access_token is True
        assert claims.token_id is None

    def test_check_ui_access_token_expired(self, django_assert_num_queries) -> None:
        now = utcnow()
        claims = UserClaims(
            user_api_id="jerry",
            username="jerry_s",
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="jambalaya",
        )

        with freeze_time(now - datetime.timedelta(minutes=40)), django_assert_num_queries(0):
            access_token, _ = generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))
        with pytest.raises(InvalidAccessTokenError, match="Signature has expired"):
            check_access_token(access_token.token)

    def test_check_ui_access_token_invalid_type(self) -> None:
        user = ToolchainUser.create(username="cosmo", email="cosmo.kramer@jerry.com")
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        with pytest.raises(InvalidAccessTokenError, match="Invalid token type"):
            check_access_token(token_str)

    def test_generate_restricted_access_token(self) -> None:
        customer = Customer.create(slug="usps", name="Postal Service")
        user = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer.add_user(user)
        repo = Repo.create("cookie", customer, "Look to the cookie")
        now = utcnow()
        access_token = generate_restricted_access_token(
            repo=repo,
            user=user,
            expiration_delta=datetime.timedelta(seconds=180),
            with_caching=False,
            token_id="tyler-chicken",
            ctx="mandelbaum",
        )
        assert isinstance(access_token, AccessToken)
        assert isinstance(access_token.token, str)
        expected_expiration = now + datetime.timedelta(seconds=180)
        assert access_token.expiration.timestamp() == pytest.approx(expected_expiration.timestamp(), 3)
        headers = jwt.get_unverified_header(access_token.token)
        key = self.current_access_token_key
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": key.key_id,
        }
        claims_dict = jwt.decode(
            access_token.token, key.secret_key, algorithms=["HS256"], options=dict(verify_aud=False)
        )

        assert claims_dict.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims_dict.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims_dict == {
            "jid": "tyler-chicken",
            "iss": "toolchain",
            "aud": ["buildsense", "impersonate"],
            "type": "access",
            "sub": "restricted",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.pk,
            "toolchain_repo": repo.pk,
            "toolchain_user": user.api_id,
            "username": "kramer",
        }

    def test_generate_restricted_access_token_with_caching(self) -> None:
        customer = Customer.create(slug="usps", name="Postal Service")
        user = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer.add_user(user)
        repo = Repo.create("cookie", customer, "Look to the cookie")
        now = utcnow()
        access_token = generate_restricted_access_token(
            repo=repo,
            user=user,
            expiration_delta=datetime.timedelta(seconds=230),
            with_caching=True,
            token_id="bob",
            ctx="mandelbaum",
        )
        assert isinstance(access_token, AccessToken)
        assert isinstance(access_token.token, str)
        assert access_token.expiration == (now + datetime.timedelta(seconds=230)).replace(microsecond=0)
        headers = jwt.get_unverified_header(access_token.token)
        key = self.current_access_token_key
        assert headers == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": key.key_id,
        }
        claims_dict = jwt.decode(
            access_token.token, key.secret_key, algorithms=["HS256"], options=dict(verify_aud=False)
        )

        assert claims_dict.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims_dict.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims_dict == {
            "jid": "bob",
            "iss": "toolchain",
            "aud": ["buildsense", "cache_rw", "impersonate"],
            "type": "access",
            "sub": "restricted",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.pk,
            "toolchain_repo": repo.pk,
            "toolchain_user": user.api_id,
            "username": "kramer",
        }

    def test_generate_access_token_from_refresh_token_inactive_repo(self, django_assert_num_queries) -> None:
        claims = repo_claims_for_test(
            "jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.REFRESH_TOKEN, customer_slug="frank"
        )
        Repo.objects.get(id=claims.repo_pk).deactivate()
        with django_assert_num_queries(1), pytest.raises(InvalidTokenRequest, match="Repo N/A"):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))

    def test_generate_access_token_from_refresh_token_inactive_customer(self, django_assert_num_queries) -> None:
        claims = repo_claims_for_test(
            "jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.REFRESH_TOKEN, customer_slug="frank"
        )
        Customer.objects.get(id=claims.customer_pk).deactivate()
        with django_assert_num_queries(1), pytest.raises(InvalidTokenRequest, match="Inactive customer org"):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))

    def test_generate_access_token_from_refresh_token_limited_customer(self, django_assert_num_queries) -> None:
        claims = repo_claims_for_test(
            "jerry", AccessTokenAudience.BUILDSENSE_API, AccessTokenType.REFRESH_TOKEN, customer_slug="frank"
        )
        customer = Customer.objects.get(id=claims.customer_pk)
        customer.set_service_level(Customer.ServiceLevel.LIMITED)
        with django_assert_num_queries(1), pytest.raises(
            InvalidTokenRequest, match="Customer org has limited functionality."
        ):
            generate_access_token_from_refresh_token(claims, datetime.timedelta(seconds=180))
