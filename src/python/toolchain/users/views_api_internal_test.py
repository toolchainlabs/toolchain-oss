# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
from rest_framework.test import APIClient

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import Customer, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_bitbucket_user, create_github_user, create_staff
from toolchain.users.models import AuthProvider, UserCustomerAccessConfig
from toolchain.users.views_api_internal import ErrorType, get_user_for_ci_username_or_user_id
from toolchain.util.test.util import assert_messages


@pytest.mark.django_db()
class TestResolveUserView:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc")

    @pytest.fixture()
    def impersonation_user(self, customer: Customer) -> ToolchainUser:
        user = create_staff(username="kramer", email="kramer@jerrysplace.com")
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
            is_org_admin=False,
        )
        customer.add_user(user)
        return user

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(username="george", email="george@jerrysplace.com", github_user_id="65333221")

    @pytest.fixture()
    def ci_user(self) -> ToolchainUser:
        return create_github_user(
            username="kenny", email="kenny@seinfeld.com", github_username="kennyk", github_user_id="78222133"
        )

    @pytest.fixture()
    def bitbucket_ci_user(self) -> ToolchainUser:
        return create_bitbucket_user(
            username="kenny", bitbucket_user_id="77383838839292", bitbucket_username="kennykramer"
        )

    def _get_client(self, user: ToolchainUser | None) -> APIClient:
        extra = {"HTTP_X_TOOLCHAIN_INTERNAL_AUTH": json.dumps({"user": {"api_id": user.api_id}})} if user else {}
        return APIClient(HTTP_X_TOOLCHAIN_INTERNAL_CALL=1, **extra)

    @pytest.fixture()
    def client(self, impersonation_user: ToolchainUser) -> APIClient:
        return self._get_client(impersonation_user)

    @pytest.fixture(params=["USER_ID", "USERNAME"])
    def query_params(self, request, ci_user: ToolchainUser) -> dict:
        if request.param == "USER_ID":
            return {"user_id": "78222133", "scm": "github"}
        return {"username": "kennyk"}

    def test_resolve_ci_user_missing_params(
        self, customer: Customer, client, impersonation_user: ToolchainUser
    ) -> None:
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", {"bob": "sacamano"})
        assert response.status_code == 400
        assert response.json() == {"detail": "Missing params."}

    def test_resolve_ci_user_missing_scm(self, customer: Customer, client, impersonation_user: ToolchainUser) -> None:
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", {"user_id": "73983113"})
        assert response.status_code == 400
        assert response.json() == {"detail": "scm param missing."}

    def test_resolve_ci_user_no_access(self, customer: Customer, ci_user: ToolchainUser, query_params: dict) -> None:
        customer.add_user(ci_user)
        client = self._get_client(user=None)
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", query_params)
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication credentials were not provided."}
        assert response.get("WWW-Authenticate") == "Missing/invalid X-Toolchain-Internal-Auth"

    def test_resolve_ci_user_can_impersonate_github(
        self,
        client: APIClient,
        customer: Customer,
        impersonation_user: ToolchainUser,
        ci_user: ToolchainUser,
        query_params: dict,
    ) -> None:
        customer.add_user(ci_user)
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", query_params)
        assert response.status_code == 200
        assert response.json() == {
            "user": {
                "username": "kenny",
                "api_id": ci_user.api_id,
                "scm": "github",
                "scm_username": "kennyk",
                "github_username": "kennyk",
            }
        }

    def test_resolve_ci_user_can_impersonate_bitbucket(
        self,
        client: APIClient,
        customer: Customer,
        impersonation_user: ToolchainUser,
        bitbucket_ci_user: ToolchainUser,
    ) -> None:
        customer.add_user(bitbucket_ci_user)
        response = client.get(
            f"/internal/api/v1/customers/{customer.pk}/users/resolve/",
            {"user_id": "77383838839292", "scm": "bitbucket"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "user": {
                "username": "kenny",
                "api_id": bitbucket_ci_user.api_id,
                "scm": "bitbucket",
                "scm_username": "kennykramer",
                "github_username": "kennykramer",
            }
        }

    def test_resolve_ci_user_impersonation_not_allowed(
        self, client: APIClient, user: ToolchainUser, ci_user: ToolchainUser, query_params: dict
    ) -> None:
        customer = Customer.create(slug="newman", name="The mail never stops", scm=Customer.Scm.BITBUCKET)
        customer.add_user(ci_user)
        customer.add_user(user)
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", query_params)
        assert response.status_code == 403
        assert response.json() == {"detail": "Impersonate permission denied."}

    def test_resolve_ci_user_not_github_by_username(
        self, client: APIClient, customer: Customer, user: ToolchainUser
    ) -> None:
        ci_user = create_bitbucket_user(
            username="kenny", bitbucket_user_id="77383838839292", bitbucket_username="kennykramer"
        )
        customer.add_user(ci_user)
        customer.add_user(user)
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", {"username": "kennykramer"})
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_resolve_ci_user_not_github_by_user_id(
        self, client: APIClient, customer: Customer, bitbucket_ci_user: ToolchainUser, user: ToolchainUser
    ) -> None:
        customer.add_user(bitbucket_ci_user)
        customer.add_user(user)
        response = client.get(
            f"/internal/api/v1/customers/{customer.pk}/users/resolve/", {"user_id": "77383838839292", "scm": "github"}
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_resolve_ci_user_self_github(self, customer: Customer, ci_user: ToolchainUser, query_params: dict) -> None:
        customer.add_user(ci_user)
        client = self._get_client(ci_user)
        response = client.get(f"/internal/api/v1/customers/{customer.pk}/users/resolve/", query_params)
        assert response.status_code == 200
        assert response.json() == {
            "user": {
                "username": "kenny",
                "api_id": ci_user.api_id,
                "scm": "github",
                "scm_username": "kennyk",
                "github_username": "kennyk",
            }
        }

    def test_resolve_ci_user_self_bitbucket(self, customer: Customer, bitbucket_ci_user: ToolchainUser) -> None:
        customer.add_user(bitbucket_ci_user)
        client = self._get_client(bitbucket_ci_user)
        response = client.get(
            f"/internal/api/v1/customers/{customer.pk}/users/resolve/",
            {"user_id": "77383838839292", "scm": "bitbucket"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "user": {
                "username": "kenny",
                "api_id": bitbucket_ci_user.api_id,
                "scm": "bitbucket",
                "scm_username": "kennykramer",
                "github_username": "kennykramer",
            }
        }


@pytest.mark.django_db()
class TestResolveCIUser:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc")

    @pytest.fixture()
    def org_admin(self, customer: Customer) -> ToolchainUser:
        user = create_github_user(username="elaine.benes", github_username="elaine", github_user_id="74991")
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
            is_org_admin=True,
        )
        return user

    def test_resolve_invalid(self, caplog, customer: Customer, org_admin: ToolchainUser) -> None:
        with pytest.raises(ToolchainAssertion, match="Must provider username or user_id"):
            get_user_for_ci_username_or_user_id(
                current_user=org_admin,
                customer_id=customer.pk,
                username=None,
                user_id=None,
                provider=AuthProvider.GITHUB,
            )

    def test_resolve_username_no_user(self, caplog, customer: Customer, org_admin: ToolchainUser) -> None:
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username="ovaltine",
            user_id=None,
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user is None
        assert gh_username is None
        assert error_type == ErrorType.NOT_FOUND
        assert_messages(caplog, "Can't resolve username")

    def test_resolve_username_dont_use_username(self, caplog, customer: Customer, org_admin: ToolchainUser) -> None:
        ci_user = create_github_user(username="ovaltine", github_username="newman", github_user_id="331441")
        customer.add_user(ci_user)
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username="ovaltine",
            user_id=None,
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user is None
        assert gh_username is None
        assert error_type == ErrorType.NOT_FOUND
        assert_messages(caplog, "Can't resolve username")

    def test_resolve_username_inactive_user(self, customer: Customer, org_admin: ToolchainUser) -> None:
        ci_user = create_github_user(username="vandelay", github_username="newman", github_user_id="73621")
        customer.add_user(ci_user)
        ci_user.deactivate()
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username="newman",
            user_id=None,
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user == ci_user
        assert error_type is None
        assert gh_username == "newman"

    def test_resolve_username(self, customer: Customer, org_admin: ToolchainUser) -> None:
        ci_user = create_github_user(username="vandelay", github_username="newman", github_user_id="3001")
        customer.add_user(ci_user)
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username="newman",
            user_id=None,
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user == ci_user
        assert error_type is None

    def test_resolve_github_user_id(self, customer: Customer, org_admin: ToolchainUser) -> None:
        ci_user = create_github_user(username="vandelay", github_username="newman", github_user_id="3001")
        customer.add_user(ci_user)
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username=None,
            user_id="3001",
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user == ci_user
        assert error_type is None

    def test_resolve_bitbucket_user_id(self, customer: Customer, org_admin: ToolchainUser) -> None:
        ci_user = create_bitbucket_user(username="vandelay", bitbucket_username="george", bitbucket_user_id="66665553")
        customer.add_user(ci_user)
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username=None,
            user_id="66665553",
            provider=AuthProvider.BITBUCKET,
        )
        assert resolved_user == ci_user
        assert error_type is None

    def test_resolve_username_not_associated_with_customer(
        self, caplog, customer: Customer, org_admin: ToolchainUser
    ) -> None:
        ci_user = create_github_user(username="vandelay", github_username="newman", github_user_id="91919")
        customer_2 = Customer.create(slug="kramer", name="Cosmo Karamer")
        customer_2.add_user(ci_user)
        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer.pk,
            username="newman",
            user_id=None,
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user is None
        assert error_type == ErrorType.NOT_FOUND
        assert gh_username is None
        assert_messages(caplog, "Can't find toolchain user for UserAuth")

        error_type, resolved_user, gh_username = get_user_for_ci_username_or_user_id(
            current_user=org_admin,
            customer_id=customer_2.pk,
            username="newman",
            user_id=None,
            provider=AuthProvider.GITHUB,
        )
        assert resolved_user is None
        assert gh_username is None
        assert error_type == ErrorType.DENIED
        assert_messages(caplog, r"missing_impersonation_permissions elaine.benes/.*")


@pytest.mark.django_db()
class TestAdminUsersView:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc")

    def test_get_admins_unknown_customer(self, client: APIClient) -> None:
        response = client.get("/internal/api/v1/customers/jerry/users/admin/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_admins_inactive_customer(self, client: APIClient, customer: Customer) -> None:
        customer.deactivate()
        response = client.get(f"/internal/api/v1/customers/{customer.id}/users/admin/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_admins_no_admins(self, client: APIClient, customer: Customer) -> None:
        response = client.get(f"/internal/api/v1/customers/{customer.id}/users/admin/")
        assert response.status_code == 200
        assert response.json() == {"admins": []}

    def test_get_admins(self, client: APIClient, customer: Customer) -> None:
        admin_user_1 = create_github_user("cosmo", github_user_id="71123", github_username="kramer")
        customer.add_user(admin_user_1)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=admin_user_1.api_id,
            audience=AccessTokenAudience.FRONTEND_API,
            is_org_admin=True,
        )
        response = client.get(f"/internal/api/v1/customers/{customer.id}/users/admin/")
        assert response.status_code == 200
        assert response.json() == {"admins": [{"username": "cosmo", "email": "cosmo@jerrysplace.com"}]}
