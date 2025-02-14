# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from django.http import HttpRequest
from freezegun import freeze_time
from rest_framework.exceptions import AuthenticationFailed, ParseError

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.claims import Claims, RepoClaims, UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.site.models import AllocatedRefreshToken, Customer, Repo, ToolchainUser
from toolchain.users.jwt.authentication import (
    AccessTokenAuthentication,
    AuthenticationFromInternalHeaders,
    RefreshTokenAuthentication,
)
from toolchain.users.jwt.utils import (
    generate_access_token_from_refresh_token,
    generate_refresh_token,
    get_or_create_refresh_token_for_ui,
)
from toolchain.users.jwt.utils_test import repo_claims_for_test
from toolchain.util.test.util import assert_messages, convert_headers_to_wsgi


def _create_fake_request(auth_header: str, headers: dict | None = None) -> HttpRequest:
    req = HttpRequest()
    if auth_header:
        req.META["HTTP_AUTHORIZATION"] = auth_header
    if headers:
        req.META.update(convert_headers_to_wsgi(headers))
    return req


@pytest.mark.django_db()
class TestRefreshTokenAuthentication:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="festivus", name="Feats of strength")

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        return user

    @pytest.mark.parametrize("header", [None, b"", ""])
    def test_no_auth_header(self, header) -> None:
        auth = RefreshTokenAuthentication()
        assert auth.authenticate(_create_fake_request(header)) is None

    @pytest.mark.parametrize(
        "header",
        [
            b"   ",
            "     ",
            "*** ****",
            b"festivus",
            "bearer some_key",  # must be Bearer
            b"bearer some_key",  # must be Bearer
        ],
    )
    def test_authentication_bad_headers(self, header: str) -> None:
        auth = RefreshTokenAuthentication()
        with pytest.raises(ParseError, match="Malformed authentication header"):
            auth.authenticate(_create_fake_request(header))

    @pytest.mark.parametrize(
        "token_str",
        [
            "I don't want to be a pirate",
            "invalid_key",
            "eyJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MSwiaXNzIjoidG9vbGNoYWluIiwiaWF0IjoxNTc0NzI3OTAwLCJ1c2VybmFtZSI6ImtyYW1lciIsInRvb2xjaGFpbl91c2VyIjoiVHFxd2FtS2pyUWRRNUhETHdpSGV6QyIsInRvb2xjaGFpbl9yZXBvIjoiaW5kZXBlbmRlbnQtZ2VvcmdlIiwidG9vbGNoYWluX2N1c3RvbWVyIjoid29ybGRzLWNvbGxpZGUifQ",
        ],
    )
    def test_authentication_malformed_jwt(self, caplog, token_str: str) -> None:
        auth = RefreshTokenAuthentication()
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="Invalid Refresh token.*Error decoding token headers")

    def test_authentication_invalid_repo_token_inactive_user(self, caplog, user: ToolchainUser) -> None:
        auth = RefreshTokenAuthentication()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        user.deactivate()
        with pytest.raises(AuthenticationFailed, match="User N/A"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match=f"No user for {user.api_id} - RepoClaims.*")

    def test_invalid_token_invalid_repo(self, caplog, user):
        auth = RefreshTokenAuthentication()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        token_str = generate_refresh_token(
            user=user,
            repo_pk="cookie",
            customer=customer,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="token_failure error=repo_mismatch token_type=refresh")

    def test_invalid_token_invalid_customer(self, caplog, user):
        auth = RefreshTokenAuthentication()
        customer_1 = Customer.create(slug="kramer", name="Kramerica Industries")
        customer_2 = Customer.create(slug="festivus", name="Feats of strength")
        repo = Repo.create("cookie", customer_1, "Look to the cookie")
        customer_1.add_user(user)
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer_2,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="token_failure error=repo_mismatch token_type=refresh")

    def test_invalid_token_invalid_customer_association(self, caplog, user):
        auth = RefreshTokenAuthentication()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="token_failure error=customer_mismatch token_type=refresh")

    def test_authentication_expired_repo_token(self, caplog, user, customer):
        auth = RefreshTokenAuthentication()
        token_str = generate_refresh_token(
            user=user,
            repo_pk="bermuda",
            customer=customer,
            expiration_time=utcnow() - datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.for_pants_client(),
            description="Maybe the dingo ate your baby!",
        )
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="Signature has expired.")

    def test_authentication_success_repo_token(self, user: ToolchainUser) -> None:
        auth = RefreshTokenAuthentication()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        token_user, claims = auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert isinstance(claims, RepoClaims)
        assert token_user == user
        assert claims.user_api_id == user.api_id
        assert claims.customer_pk == customer.pk
        assert claims.repo_pk == repo.id
        assert claims.audience == AccessTokenAudience.DEPENDENCY_API
        assert claims.restricted is False

    def test_authentication_success_ui_token(self, user: ToolchainUser) -> None:
        auth = RefreshTokenAuthentication()
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        token_user, claims = auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert isinstance(claims, UserClaims)
        assert token_user == user
        assert claims.user_api_id == user.api_id
        assert claims.audience == AccessTokenAudience.FRONTEND_API

    def test_unknown_token_id(self, user, caplog):
        auth = RefreshTokenAuthentication()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        assert AllocatedRefreshToken.objects.count() == 1
        assert AllocatedRefreshToken.objects.first().delete()
        assert AllocatedRefreshToken.objects.count() == 0
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="token_failure error=unknown_token_id token_type=refresh")

    def test_revoked_repo_token(self, user, caplog):
        auth = RefreshTokenAuthentication()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=customer,
            expiration_time=utcnow() + datetime.timedelta(minutes=1),
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="Maybe the dingo ate your baby!",
        )
        assert AllocatedRefreshToken.objects.count() == 1
        assert AllocatedRefreshToken.objects.first().revoke() is True
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="token_failure error=inactive_token token_type=refresh")

    def test_revoked_ui_token(self, user, caplog):
        auth = RefreshTokenAuthentication()
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        assert AllocatedRefreshToken.objects.count() == 1
        assert AllocatedRefreshToken.objects.first().revoke() is True
        with pytest.raises(AuthenticationFailed, match="Invalid Refresh Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="token_failure error=inactive_token token_type=refresh")


@pytest.mark.django_db()
class TestAccessTokenAuthentication:
    @pytest.fixture()
    def user(self):
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        return user

    @pytest.mark.parametrize("header", [None, b"", ""])
    def test_no_auth_header(self, header) -> None:
        auth = AccessTokenAuthentication()
        assert auth.authenticate(_create_fake_request(header)) is None

    @pytest.mark.parametrize(
        "header",
        [
            b"   ",
            "     ",
            "*** ****",
            b"festivus",
            "bearer some_key",  # must be Bearer
            b"bearer some_key",  # must be Bearer
        ],
    )
    def test_access_token_authentication_bad_headers(self, header) -> None:
        auth = AccessTokenAuthentication()
        with pytest.raises(ParseError, match="Malformed authentication header"):
            auth.authenticate(_create_fake_request(header))

    @pytest.mark.parametrize(
        "token_str",
        [
            "I don't want to be a pirate",
            "invalid_key",
            "eyJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6MSwiaXNzIjoidG9vbGNoYWluIiwiaWF0IjoxNTc0NzI3OTAwLCJ1c2VybmFtZSI6ImtyYW1lciIsInRvb2xjaGFpbl91c2VyIjoiVHFxd2FtS2pyUWRRNUhETHdpSGV6QyIsInRvb2xjaGFpbl9yZXBvIjoiaW5kZXBlbmRlbnQtZ2VvcmdlIiwidG9vbGNoYWluX2N1c3RvbWVyIjoid29ybGRzLWNvbGxpZGUifQ",
        ],
    )
    def test_authentication_malformed_jwt(self, caplog, token_str: str) -> None:
        auth = AccessTokenAuthentication()
        with pytest.raises(AuthenticationFailed, match="Invalid Access Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="Invalid Access token.*Error decoding token headers")

    def test_authentication_invalid_token_inactive_user(self, caplog, user: ToolchainUser) -> None:
        auth = AccessTokenAuthentication()
        token_str = generate_access_token_from_refresh_token(
            repo_claims_for_test(user, AccessTokenAudience.DEPENDENCY_API, AccessTokenType.REFRESH_TOKEN),
            expiration_delta=datetime.timedelta(minutes=19),
        )[0].token
        user.deactivate()
        with pytest.raises(AuthenticationFailed, match="User N/A"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match=f"No user for {user.api_id} - RepoClaims.*")

    def test_authentication_expired_token(self, caplog, user: ToolchainUser) -> None:
        auth = AccessTokenAuthentication()
        with freeze_time(utcnow() - datetime.timedelta(minutes=10)):
            token_str = generate_access_token_from_refresh_token(
                repo_claims_for_test(user, AccessTokenAudience.DEPENDENCY_API, AccessTokenType.REFRESH_TOKEN),
                expiration_delta=datetime.timedelta(minutes=3),
            )[0].token
        with pytest.raises(AuthenticationFailed, match="Invalid Access Token"):
            auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert_messages(caplog, match="Signature has expired.")

    def test_authentication_success(self, user: ToolchainUser) -> None:
        auth = AccessTokenAuthentication()
        fake_claims = repo_claims_for_test(user, AccessTokenAudience.DEPENDENCY_API, AccessTokenType.REFRESH_TOKEN)
        repo = Repo.objects.get(id=fake_claims.repo_pk)
        token_str = generate_access_token_from_refresh_token(
            fake_claims, expiration_delta=datetime.timedelta(minutes=19)
        )[0].token
        token_user, claims = auth.authenticate(_create_fake_request(f"Bearer {token_str}"))
        assert token_user == user
        assert claims.user_api_id == user.api_id
        assert claims.customer_pk == repo.customer_id
        assert claims.repo_pk == repo.id
        assert claims.audience == AccessTokenAudience.DEPENDENCY_API

    def test_access_token_success_with_impersonation(self, user):
        auth = AccessTokenAuthentication()
        fake_claims = repo_claims_for_test(
            user, AccessTokenAudience.for_pants_client(with_impersonation=True), AccessTokenType.REFRESH_TOKEN
        )
        repo = Repo.objects.get(id=fake_claims.repo_pk)
        token_str = generate_access_token_from_refresh_token(
            fake_claims, expiration_delta=datetime.timedelta(minutes=19)
        )[0].token
        req = _create_fake_request(f"Bearer {token_str}", headers={"X-Toolchain-Impersonate": "top-of-the-muffin"})
        token_user, claims = auth.authenticate(req)
        assert token_user == user
        assert claims.user_api_id == user.api_id
        assert claims.customer_pk == repo.customer_id
        assert claims.repo_pk == repo.id
        assert claims.impersonated_user_api_id == "top-of-the-muffin"
        assert (
            claims.audience
            == AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.IMPERSONATE
        )


def _create_fake_internal_request(
    is_toolchain_internal_call: bool | None = None, user: ToolchainUser | None = None, claims: Claims | None = None
) -> HttpRequest:
    req = HttpRequest()
    req.path = "/soup/jerry"
    if is_toolchain_internal_call is not None:
        req.is_toolchain_internal_call = is_toolchain_internal_call
    req.internal_service_call_user = user
    req.toolchain_claims = claims
    return req


@pytest.mark.django_db()
class TestAuthenticationFromInternalHeaders:
    def test_internal_call_not_set(self) -> None:
        auth = AuthenticationFromInternalHeaders()
        assert auth.authenticate(_create_fake_internal_request()) is None

    def test_not_internal_call(self) -> None:
        auth = AuthenticationFromInternalHeaders()
        assert auth.authenticate(_create_fake_internal_request(False)) is None

    def test_internal_call_no_user(self) -> None:
        auth = AuthenticationFromInternalHeaders()
        assert auth.authenticate(_create_fake_internal_request(True)) is None

    def test_with_user_and_claims(self):
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        claims = RepoClaims(
            user_api_id="oppsite",
            customer_pk="jor-el",
            repo_pk="bosco",
            username="darren",
            audience=AccessTokenAudience.BUILDSENSE_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            restricted=False,
        )

        auth = AuthenticationFromInternalHeaders()
        req = _create_fake_internal_request(True, user=user, claims=claims)
        res = auth.authenticate(req)
        assert res is not None
        assert isinstance(res, tuple)
        assert len(res) == 2
        assert res[0] == user
        assert res[1] == claims
