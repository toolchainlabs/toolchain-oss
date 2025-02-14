# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from unittest import mock

import pytest
from django.views import View
from rest_framework.permissions import BasePermission

from toolchain.django.auth.claims import RepoClaims, UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.site.models import Customer, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_staff
from toolchain.users.jwt.permissions import AccessTokensPermissions
from toolchain.util.test.util import assert_messages


class FakeFrontEndView(View):
    audience = AccessTokenAudience.FRONTEND_API


class FakeBuildsenseView(View):
    audience = AccessTokenAudience.BUILDSENSE_API


class FakeDependencyView(View):
    audience = AccessTokenAudience.DEPENDENCY_API


def _create_simple_fake_request(audience: AccessTokenAudience, claim_ver: int) -> mock.MagicMock:
    claims_dict = {
        "toolchain_claims_ver": claim_ver,
        "toolchain_user": "elaine_dance",
        "toolchain_repo": "sweet_fancy_moses",
        "toolchain_customer": "make_a_with",
        "username": "darren",
        "jid": "soup",
    }
    if claim_ver > 1:
        claims_dict["type"] = "refresh"
    return mock.MagicMock(auth=RepoClaims.create_repo_claims(claims_dict, audience, None))


def _create_impersonation_fake_request(
    audience: AccessTokenAudience, customer_id: str, user: ToolchainUser, impersonate_user_api_id: str
) -> mock.MagicMock:
    # Not usingRepoClaims to be able to create "Invalid" claims to make sure we protect against bugs
    # in multiple places.
    claims = RepoClaims(
        user_api_id=user.api_id,
        repo_pk="sweet_fancy_moses",
        customer_pk=customer_id,
        username="darren",
        token_type=AccessTokenType.ACCESS_TOKEN,
        audience=audience,
        token_id=None,
        impersonated_user_api_id=impersonate_user_api_id,
        restricted=False,
    )
    return mock.MagicMock(user=user, auth=claims)


@pytest.mark.parametrize("permission_cls", [AccessTokensPermissions])
@pytest.mark.parametrize("claim_ver", [1, 2])
def test_access_token_permissions(claim_ver: int, permission_cls: type[BasePermission]) -> None:
    permissions = permission_cls()
    req = _create_simple_fake_request(AccessTokenAudience.BUILDSENSE_API, claim_ver)
    assert permissions.has_permission(request=req, view=FakeDependencyView) is False
    assert permissions.has_permission(request=req, view=FakeBuildsenseView) is True

    req = _create_simple_fake_request(AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE, claim_ver)
    assert permissions.has_permission(request=req, view=FakeDependencyView) is False
    assert permissions.has_permission(request=req, view=FakeBuildsenseView) is True

    req = _create_simple_fake_request(AccessTokenAudience.for_pants_client(), claim_ver)
    assert permissions.has_permission(request=req, view=FakeDependencyView) is False
    assert permissions.has_permission(request=req, view=FakeBuildsenseView) is True

    req = _create_simple_fake_request(AccessTokenAudience.for_pants_client(with_impersonation=True), claim_ver)
    assert permissions.has_permission(request=req, view=FakeDependencyView) is False
    assert permissions.has_permission(request=req, view=FakeBuildsenseView) is True


def test_no_auth() -> None:
    permissions = AccessTokensPermissions()
    req = mock.MagicMock(auth=None)
    assert permissions.has_permission(request=req, view=FakeDependencyView) is False
    assert permissions.has_permission(request=req, view=FakeBuildsenseView) is False


def test_user_claims() -> None:
    permissions = AccessTokensPermissions()
    claims = UserClaims(
        user_api_id="newman",
        username="hello-newman",
        audience=AccessTokenAudience.FRONTEND_API,
        token_type=AccessTokenType.ACCESS_TOKEN,
        token_id=None,
    )
    req = mock.MagicMock(auth=claims)
    assert permissions.has_permission(req, view=FakeDependencyView) is False
    assert permissions.has_permission(req, view=FakeFrontEndView) is True


@pytest.mark.django_db()
def test_impersonation() -> None:
    customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
    org_admin = create_staff(username="jerry", email="jerry@seinfeld.com")
    user = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
    customer.add_user(org_admin)
    customer.add_user(user)

    permissions = AccessTokensPermissions()
    req = _create_impersonation_fake_request(
        AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
        customer_id=customer.pk,
        user=org_admin,
        impersonate_user_api_id=user.api_id,
    )
    assert permissions.has_permission(request=req, view=FakeDependencyView) is False
    assert permissions.has_permission(request=req, view=FakeBuildsenseView) is True


@pytest.mark.django_db()
def test_impersonation_denied(caplog) -> None:
    customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
    customer_2 = Customer.create(slug="usps", name="Postal Service")
    org_admin = create_staff(username="jerry", email="jerry@seinfeld.com")
    user = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")

    customer_1.add_user(org_admin)
    customer_1.add_user(user)
    customer_2.add_user(user)

    permissions = AccessTokensPermissions()
    req_invalid_customer = _create_impersonation_fake_request(
        AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
        customer_id=customer_2.pk,
        user=org_admin,
        impersonate_user_api_id=user.api_id,
    )
    req_non_admin_user = _create_impersonation_fake_request(
        AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
        customer_id=customer_1.pk,
        user=user,
        impersonate_user_api_id=org_admin.api_id,
    )
    req_admin_not_in_customer = _create_impersonation_fake_request(
        AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
        customer_id=customer_2.pk,
        user=org_admin,
        impersonate_user_api_id=user.api_id,
    )
    req_missing_permission = _create_impersonation_fake_request(
        AccessTokenAudience.BUILDSENSE_API,
        customer_id=customer_1.pk,
        user=org_admin,
        impersonate_user_api_id=user.api_id,
    )

    assert permissions.has_permission(request=req_invalid_customer, view=FakeBuildsenseView) is False
    assert_messages(caplog, r"tried to impersonate.*and was denied.")

    assert permissions.has_permission(request=req_non_admin_user, view=FakeBuildsenseView) is True
    assert_messages(caplog, r"tried to impersonate.*and was denied.")

    assert permissions.has_permission(request=req_admin_not_in_customer, view=FakeBuildsenseView) is False
    assert_messages(caplog, r"tried to impersonate.*and was denied.")

    assert permissions.has_permission(request=req_missing_permission, view=FakeBuildsenseView) is False
    assert_messages(caplog, r"Impersonation specified .* without proper permission")
