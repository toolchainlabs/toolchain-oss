# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.claims import UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.models import (
    AccessTokenState,
    AccessTokenUsage,
    AllocatedRefreshToken,
    Customer,
    Repo,
    ToolchainUser,
)
from toolchain.django.site.test_helpers.models_helpers import create_github_user
from toolchain.github_integration.client.repo_clients_test import add_get_install_info_response
from toolchain.payments.client.customer_client_test import add_get_plan_and_usage_response
from toolchain.payments.stripe_integration.client.customer_client_test import (
    add_create_portal_session_response,
    assert_create_portal_session_request,
)
from toolchain.users.models import AuthProvider, OptionalBool, RemoteExecWorkerToken, UserAuth, UserCustomerAccessConfig
from toolchain.util.test.util import assert_messages, convert_headers_to_wsgi


@pytest.mark.django_db()
class BaseViewsTest:
    @pytest.fixture()
    def user(self, client) -> ToolchainUser:
        return create_github_user(username="kramer", email="kramer@jerrysplace.com")

    @pytest.fixture()
    def other_user(self, client) -> ToolchainUser:
        return create_github_user(
            username="otheruser", email="wilie@coyote.com", github_user_id="88842", github_username="wilie"
        )

    @pytest.fixture()
    def customer(self, user: ToolchainUser) -> Customer:
        customer = Customer.create(slug="acmeid", name="acme")
        customer.maybe_set_logo("https://festivus.com/pole")
        customer.add_user(user)
        return customer

    @pytest.fixture()
    def bitbucket_customer(self, user: ToolchainUser) -> Customer:
        customer = Customer.create(slug="seinfeld", name="Jerry Seinfeld", scm=Customer.Scm.BITBUCKET)
        customer.maybe_set_logo("https://nbc.com/toms")
        customer.add_user(user)
        return customer

    @pytest.fixture()
    def other_customer(self, other_user: ToolchainUser) -> Customer:
        customer = Customer.create(slug="othercustomer", name="other_customer_name")
        customer.add_user(other_user)
        return customer

    @pytest.fixture()
    def client(self, user: ToolchainUser) -> APIClient:
        return self._get_client(user)

    def _get_client(self, user: ToolchainUser) -> APIClient:
        claims = UserClaims(
            user_api_id=user.api_id,
            username=user.username,
            audience=AccessTokenAudience.FRONTEND_API,
            token_type=AccessTokenType.ACCESS_TOKEN,
            token_id=None,
        )
        headers = create_internal_auth_headers(user, claims=claims.as_json_dict(), impersonation=None)
        return APIClient(**convert_headers_to_wsgi(headers))

    def _create_uac(self, customer: Customer, user: ToolchainUser, is_admin: bool) -> None:
        UserCustomerAccessConfig.create_readwrite(
            customer_id=customer.id, user_api_id=user.api_id, is_org_admin=OptionalBool.from_bool(is_admin)
        )


class TestToolchainUserViewSet(BaseViewsTest):
    def test_unauthenticated_get_me(self) -> None:
        response = APIClient().get("/api/v1/users/me/")
        assert response.status_code == 403

    def test_get_users(self, client) -> None:
        assert client.get("/api/v1/users/").status_code == 404

    def test_get_user(self, client, user: ToolchainUser) -> None:
        user.full_name = "Cosmo Kramer"
        user.save()
        response = client.get(f"/api/v1/users/{user.api_id}/")

        assert response.status_code == 200
        assert response.json() == {
            "api_id": user.api_id,
            "email": "kramer@jerrysplace.com",
            "avatar_url": "https://pictures.jerry.com/gh-kramer",
            "full_name": "Cosmo Kramer",
            "username": "kramer",
        }

    def test_get_user_as_me(self, client, user: ToolchainUser) -> None:
        user.full_name = "Kenny not-kramer"
        user.save()
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert response.json() == {
            "api_id": user.api_id,
            "email": "kramer@jerrysplace.com",
            "full_name": "Kenny not-kramer",
            "avatar_url": "https://pictures.jerry.com/gh-kramer",
            "username": "kramer",
        }

    def test_get_user_other_user(self, client, user: ToolchainUser, other_user: ToolchainUser) -> None:
        response = client.get(f"/api/v1/users/{other_user.api_id}/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def _get_repos_response(self, client, django_assert_num_queries) -> list[dict]:
        with django_assert_num_queries(2):
            response = client.get("/api/v1/users/repos/")
        assert response.status_code == 200
        return response.json()

    def test_get_user_repos(self, client, django_assert_num_queries, user: ToolchainUser) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_1.maybe_set_logo("https://feats.com/of-stength")
        customer_2 = Customer.create(slug="usps", name="Postal Service", scm=Customer.Scm.BITBUCKET)
        repo_1_1 = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_1_2 = Repo.create("mailbox", customer_1, "Mail never stops")
        repo_2_1 = Repo.create("submarine", customer_2, "Turn your key")
        repo_2_2 = Repo.create("buzzer", customer_2, "strongbox")

        assert self._get_repos_response(client, django_assert_num_queries) == []

        customer_1.add_user(user)
        assert self._get_repos_response(client, django_assert_num_queries) == [
            {
                "id": repo_1_1.id,
                "name": "Look to the cookie",
                "customer_id": customer_1.id,
                "slug": "cookie",
                "customer_slug": "jerry",
                "customer_logo": "https://feats.com/of-stength",
                "customer_link": "https://github.com/jerry/",
                "repo_link": "https://github.com/jerry/cookie/",
                "scm": "github",
            },
            {
                "id": repo_1_2.id,
                "name": "Mail never stops",
                "customer_id": customer_1.id,
                "slug": "mailbox",
                "customer_slug": "jerry",
                "customer_logo": "https://feats.com/of-stength",
                "customer_link": "https://github.com/jerry/",
                "repo_link": "https://github.com/jerry/mailbox/",
                "scm": "github",
            },
        ]

        customer_2.add_user(user)
        assert self._get_repos_response(client, django_assert_num_queries) == [
            {
                "customer_id": customer_2.id,
                "customer_slug": "usps",
                "id": repo_2_2.id,
                "name": "strongbox",
                "slug": "buzzer",
                "customer_link": "https://bitbucket.org/usps/",
                "repo_link": "https://bitbucket.org/usps/buzzer/",
                "scm": "bitbucket",
                "customer_logo": "",
            },
            {
                "id": repo_1_1.id,
                "name": "Look to the cookie",
                "customer_id": customer_1.id,
                "slug": "cookie",
                "customer_slug": "jerry",
                "customer_logo": "https://feats.com/of-stength",
                "customer_link": "https://github.com/jerry/",
                "repo_link": "https://github.com/jerry/cookie/",
                "scm": "github",
            },
            {
                "id": repo_1_2.id,
                "name": "Mail never stops",
                "customer_id": customer_1.id,
                "slug": "mailbox",
                "customer_slug": "jerry",
                "customer_logo": "https://feats.com/of-stength",
                "customer_link": "https://github.com/jerry/",
                "repo_link": "https://github.com/jerry/mailbox/",
                "scm": "github",
            },
            {
                "customer_id": customer_2.id,
                "customer_slug": "usps",
                "id": repo_2_1.id,
                "name": "Turn your key",
                "slug": "submarine",
                "customer_logo": "",
                "customer_link": "https://bitbucket.org/usps/",
                "repo_link": "https://bitbucket.org/usps/submarine/",
                "scm": "bitbucket",
            },
        ]

    def test_get_user_emails_no_emails(self, client, user: ToolchainUser, django_assert_num_queries) -> None:
        auth = UserAuth.objects.get(user_api_id=user.api_id)
        auth._email_addresses = ""
        auth.save()
        with django_assert_num_queries(2):
            response = client.get("/api/v1/users/emails/")
        assert response.status_code == 200
        assert response.json() == {"emails": []}

    def test_get_user_emails(self, django_assert_num_queries) -> None:
        user = ToolchainUser.create(username="kenny", email="kenny.kramer@jerrysplace.com")
        UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="98222",
            username="cosmo",
            emails=["kenny@seinfeld.com", "kenny@nyc.com"],
        )
        client = self._get_client(user)
        with django_assert_num_queries(2):
            response = client.get("/api/v1/users/emails/")
        assert response.status_code == 200
        assert response.json() == {"emails": ["kenny@nyc.com", "kenny@seinfeld.com"]}

    def _add_emails(self, user, emails):
        UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="98222",
            username="cosmo",
            emails=emails,
        )

    def test_update_user_full_name(self, client, user: ToolchainUser) -> None:
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"full_name": "Bob Sacamano"})
        assert response.status_code == 200
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.full_name == "Bob Sacamano"

    def test_update_user_email_invalid_email(self, client, user: ToolchainUser) -> None:
        self._add_emails(user, emails=["kenny@seinfeld.com", "kenny@nyc.com"])
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"email": "bob@sacamano"})
        assert response.status_code == 400
        assert response.json() == {"email": ["Enter a valid email address."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.email == "kramer@jerrysplace.com" == user.email

    def test_update_user_email_not_allowed(self, client, user: ToolchainUser) -> None:
        self._add_emails(user, emails=["kenny@seinfeld.com", "kenny@nyc.com"])
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"email": "cosmo@nyc.com"})
        assert response.status_code == 400
        assert response.json() == {"email": ["Email not allowed."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.email == "kramer@jerrysplace.com" == user.email

    def test_update_user_email(self, client, user: ToolchainUser) -> None:
        self._add_emails(user, emails=["kenny@seinfeld.com", "kenny@nyc.com"])
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"email": "kenny@nyc.com"})
        assert response.status_code == 200
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.email == "kenny@nyc.com"

    def test_update_username(self, client, user: ToolchainUser) -> None:
        assert user.username == "kramer"  # sanity check
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": "cosmo"})
        assert response.status_code == 200
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "cosmo"

    @pytest.mark.parametrize("new_username", ["  cosmo", "  cosmo ", "\n cosmo ", "\t\tcosmo", "cosmo\t\n"])
    def test_update_username_strip(self, client, user: ToolchainUser, new_username: str) -> None:
        assert user.username == "kramer"  # sanity check
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": new_username})
        assert response.status_code == 200
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "cosmo"

    def test_update_username_same(self, client, user: ToolchainUser) -> None:
        assert user.username == "kramer"  # sanity check
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": "kramer"})
        assert response.status_code == 200
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "kramer"

    def test_update_username_duplicate_active(self, client, user: ToolchainUser) -> None:
        assert user.username == "kramer"  # sanity check
        create_github_user(username="cosmo", email="kenny@coyote.com", github_user_id="731233", github_username="k-man")
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": "cosmo"})
        assert response.status_code == 400
        assert response.json() == {"username": ["A user with that username already exists."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "kramer"

    @pytest.mark.parametrize("new_username", [" x", "  cos ", " cosm  ", "\t\tco", "com"])
    def test_update_username_short(self, client, user: ToolchainUser, new_username: str) -> None:
        assert user.username == "kramer"  # sanity check
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": new_username})
        assert response.status_code == 400
        assert response.json() == {"username": ["username must be at least 5 characters."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "kramer"

    @pytest.mark.parametrize("blank_username", [" ", "  \t ", "\t\n \t "])
    def test_update_username_blank(self, client, user: ToolchainUser, blank_username: str) -> None:
        assert user.username == "kramer"  # sanity check
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": blank_username})
        assert response.status_code == 400
        assert response.json() == {"username": ["This field may not be blank."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "kramer"

    def test_update_username_duplicate_inactive(self, client, user: ToolchainUser) -> None:
        assert user.username == "kramer"  # sanity check
        other = create_github_user(
            username="cosmo", email="kenny@coyote.com", github_user_id="731233", github_username="k-man"
        )
        other.deactivate()
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={"username": "cosmo"})
        assert response.status_code == 400
        assert response.json() == {"username": ["A user with that username already exists."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.username == "kramer"

    @pytest.mark.parametrize("field_name", ["id", "api_id", "first_name", "last_name", "avatar_url"])
    def test_update_user_invalid_field(self, client, user: ToolchainUser, field_name: str) -> None:
        response = client.patch(f"/api/v1/users/{user.api_id}/", data={field_name: "bob"})
        assert response.status_code == 400
        assert response.json() == {field_name: ["Update not allowed."]}
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert getattr(loaded_user, field_name) == getattr(user, field_name)

    def test_update_user_invalid_fields(self, client, user: ToolchainUser) -> None:
        response = client.patch(
            f"/api/v1/users/{user.api_id}/",
            data={"first_name": "Jerry", "last_name": "Seinfeld", "email": "jerry@email.seinfeld.com"},
        )
        assert response.status_code == 400
        assert response.json() == {
            "first_name": ["Update not allowed."],
            "last_name": ["Update not allowed."],
        }
        loaded_user = ToolchainUser.get_by_api_id(user.api_id)
        assert loaded_user.email == "kramer@jerrysplace.com"
        assert loaded_user.first_name == ""
        assert loaded_user.last_name == ""


class TestCustomerViewSet(BaseViewsTest):
    def test_get_customers_as_me(self, client, customer: Customer) -> None:
        response = client.get("/api/v1/users/me/customers/")

        assert response.status_code == 200
        assert response.json() == {
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": customer.pk,
                    "name": "acme",
                    "slug": "acmeid",
                    "customer_link": "https://github.com/acmeid/",
                    "scm": "github",
                    "logo_url": "https://festivus.com/pole",
                    "status": "free_trial",
                }
            ],
        }

    def test_get_customers(self, client, user: ToolchainUser, customer: Customer) -> None:
        customer.set_service_level(Customer.ServiceLevel.LIMITED)
        response = client.get(f"/api/v1/users/{user.api_id}/customers/")
        assert response.status_code == 200
        assert response.json() == {
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": customer.pk,
                    "name": "acme",
                    "slug": "acmeid",
                    "customer_link": "https://github.com/acmeid/",
                    "scm": "github",
                    "logo_url": "https://festivus.com/pole",
                    "status": "limited",
                }
            ],
        }

    def test_get_customers_with_query_params(self, client, user: ToolchainUser, customer: Customer) -> None:
        customer._customer_type = Customer.Type.CUSTOMER.value
        customer.save()
        customer_2 = Customer.create(slug="acmeid2", name="acme2")
        customer_2.add_user(user)

        first_page = client.get(f"/api/v1/users/{user.api_id}/customers/", {"page_size": 1})

        assert first_page.status_code == 200
        first_page_json = first_page.json()
        assert first_page_json["results"] == [
            {
                "id": customer.pk,
                "name": "acme",
                "slug": "acmeid",
                "customer_link": "https://github.com/acmeid/",
                "scm": "github",
                "logo_url": "https://festivus.com/pole",
            }
        ]

        second_page = client.get(
            f"/api/v1/users/{user.api_id}/customers/", {"cursor": first_page_json["next"], "page_size": 1}
        )

        assert second_page.status_code == 200
        second_page_json = second_page.json()
        assert len(second_page_json["results"]) == 1

        first_page_again = client.get(
            f"/api/v1/users/{user.api_id}/customers/", {"cursor": second_page_json["previous"], "page_size": 1}
        )
        assert first_page_again.status_code == 200
        assert first_page_again.json() == first_page_json

    def test_get_customers_restricted(self, client, other_user: ToolchainUser) -> None:
        response = client.get(f"/api/v1/users/{other_user.api_id}/customers/")
        assert response.status_code == 404

    def test_get_customer(self, client, user: ToolchainUser, customer: Customer) -> None:
        response = client.get(f"/api/v1/users/{user.api_id}/customers/{customer.pk}/")
        assert response.status_code == 200
        assert response.json() == {
            "id": customer.pk,
            "name": "acme",
            "slug": "acmeid",
            "customer_link": "https://github.com/acmeid/",
            "scm": "github",
            "logo_url": "https://festivus.com/pole",
            "status": "free_trial",
        }

    def test_get_customer_restricted(self, client, other_user: ToolchainUser) -> None:
        response = client.get(f"/api/v1/users/{other_user.api_id}/customers/othercustomer/")

        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}


class TestAllocatedTokensView(BaseViewsTest):
    def _allocate_ui_tokens(self, user: ToolchainUser) -> None:
        AllocatedRefreshToken.get_or_allocate_ui_token(
            user_api_id=user.api_id, ttl=datetime.timedelta(days=26)
        ).revoke()
        AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(days=10))

    def _allocate_api_tokens(
        self,
        base_time: datetime.datetime,
        count: int,
        repo: Repo,
        user: ToolchainUser,
        audience: AccessTokenAudience = AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW,
    ) -> list[str]:
        token_ids = []

        for i in range(count):
            token_id = AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=base_time,
                expires_at=base_time + datetime.timedelta(minutes=i + 10),
                description=f"Moles — freckles’ ugly cousin - {i+1}",
                repo_id=repo.id,
                audience=audience,
            )
            token_ids.append(token_id)
        return token_ids

    def test_get_allocated_tokens_empty(self, client: APIClient, user: ToolchainUser) -> None:
        self._allocate_ui_tokens(user)
        response = client.get("/api/v1/tokens/")
        assert response.status_code == 200
        assert response.json() == {"max_reached": False, "max_tokens": 25, "tokens": []}

    def test_get_allocated_tokens(self, client: APIClient, customer: Customer, user: ToolchainUser) -> None:
        bt1 = datetime.datetime(2020, 3, 29, 13, 45, 19, tzinfo=datetime.timezone.utc)
        bt2 = datetime.datetime(2020, 2, 8, 22, tzinfo=datetime.timezone.utc)
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        repo_2 = Repo.create("mailbox", customer, "Mail never stops")
        self._allocate_ui_tokens(user)
        token_ids_repo_1 = self._allocate_api_tokens(bt1, count=3, repo=repo_1, user=user)
        token_ids_repo_2 = self._allocate_api_tokens(
            bt2, count=2, repo=repo_2, user=user, audience=AccessTokenAudience.CACHE_RO
        )
        AllocatedRefreshToken.objects.get(id=token_ids_repo_1[0]).revoke()
        AllocatedRefreshToken.objects.filter(id=token_ids_repo_1[0]).update(
            last_seen=datetime.datetime(2020, 2, 10, 13, 44, 51, tzinfo=datetime.timezone.utc)
        )
        AllocatedRefreshToken.objects.filter(id=token_ids_repo_2[1]).update(
            last_seen=datetime.datetime(2020, 3, 10, 8, 4, 53, tzinfo=datetime.timezone.utc), _token_state="expired"
        )

        response = client.get("/api/v1/tokens/")
        assert response.status_code == 200
        assert response.json() == {
            "max_reached": False,
            "max_tokens": 25,
            "tokens": [
                {
                    "id": token_ids_repo_1[2],
                    "issued_at": "2020-03-29T13:45:19+00:00",
                    "expires_at": "2020-03-29T13:57:19+00:00",
                    "last_seen": None,
                    "description": "Moles — freckles’ ugly cousin - 3",
                    "state": "Active",
                    "can_revoke": True,
                    "permissions": ["buildsense", "cache_rw"],
                    "repo": {"id": repo_1.id, "name": "Look to the cookie", "slug": "cookie"},
                    "customer": {"id": customer.id, "name": "acme", "slug": "acmeid"},
                },
                {
                    "id": token_ids_repo_1[1],
                    "issued_at": "2020-03-29T13:45:19+00:00",
                    "expires_at": "2020-03-29T13:56:19+00:00",
                    "last_seen": None,
                    "description": "Moles — freckles’ ugly cousin - 2",
                    "state": "Active",
                    "can_revoke": True,
                    "permissions": ["buildsense", "cache_rw"],
                    "repo": {"id": repo_1.id, "name": "Look to the cookie", "slug": "cookie"},
                    "customer": {"id": customer.id, "name": "acme", "slug": "acmeid"},
                },
                {
                    "id": token_ids_repo_1[0],
                    "issued_at": "2020-03-29T13:45:19+00:00",
                    "expires_at": "2020-03-29T13:55:19+00:00",
                    "last_seen": "2020-02-10T13:44:51+00:00",
                    "description": "Moles — freckles’ ugly cousin - 1",
                    "state": "Revoked",
                    "can_revoke": False,
                    "permissions": ["buildsense", "cache_rw"],
                    "repo": {"id": repo_1.id, "name": "Look to the cookie", "slug": "cookie"},
                    "customer": {"id": customer.id, "name": "acme", "slug": "acmeid"},
                },
                {
                    "id": token_ids_repo_2[1],
                    "issued_at": "2020-02-08T22:00:00+00:00",
                    "expires_at": "2020-02-08T22:11:00+00:00",
                    "last_seen": "2020-03-10T08:04:53+00:00",
                    "description": "Moles — freckles’ ugly cousin - 2",
                    "state": "Expired",
                    "can_revoke": False,
                    "permissions": ["cache_ro"],
                    "repo": {"id": repo_2.id, "name": "Mail never stops", "slug": "mailbox"},
                    "customer": {"id": customer.id, "name": "acme", "slug": "acmeid"},
                },
                {
                    "id": token_ids_repo_2[0],
                    "issued_at": "2020-02-08T22:00:00+00:00",
                    "expires_at": "2020-02-08T22:10:00+00:00",
                    "last_seen": None,
                    "description": "Moles — freckles’ ugly cousin - 1",
                    "state": "Active",
                    "can_revoke": True,
                    "permissions": ["cache_ro"],
                    "repo": {"id": repo_2.id, "name": "Mail never stops", "slug": "mailbox"},
                    "customer": {"id": customer.id, "name": "acme", "slug": "acmeid"},
                },
            ],
        }

    def test_get_allocated_tokens_max_reached(self, client: APIClient, customer: Customer, user: ToolchainUser) -> None:
        bt = utcnow() + datetime.timedelta(seconds=10)
        repo = Repo.create("cookie", customer, "Look to the cookie")
        self._allocate_ui_tokens(user)
        self._allocate_api_tokens(
            bt, count=AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API], repo=repo, user=user
        )
        response = client.get("/api/v1/tokens/")
        assert response.status_code == 200
        json_response = response.json()
        tokens = json_response.pop("tokens")
        assert isinstance(tokens, list)
        assert len(tokens) == 25
        assert json_response == {"max_reached": True, "max_tokens": 25}

    def test_revoke_token(self, client: APIClient, customer: Customer, user: ToolchainUser) -> None:
        repo = Repo.create("cookie", customer, "Look to the cookie")
        bt1 = datetime.datetime(2020, 5, 13, 4, 45, 19, tzinfo=datetime.timezone.utc)
        self._allocate_ui_tokens(user)
        token_ids = self._allocate_api_tokens(bt1, count=6, repo=repo, user=user)
        token_id = token_ids[4]
        response = client.delete(f"/api/v1/tokens/{token_id}/")
        assert response.status_code == 201
        assert response.json() == {"result": "ok"}
        token = AllocatedRefreshToken.objects.get(id=token_id)
        assert token.is_active is False
        assert token.state == AllocatedRefreshToken.State.REVOKED

    def test_revoke_token_404(
        self, client: APIClient, customer: Customer, user: ToolchainUser, other_user: ToolchainUser
    ) -> None:
        repo = Repo.create("cookie", customer, "Look to the cookie")
        bt1 = datetime.datetime(2020, 5, 13, 4, 45, 19, tzinfo=datetime.timezone.utc)
        self._allocate_ui_tokens(user)
        self._allocate_api_tokens(bt1, count=6, repo=repo, user=user)
        token_ids_user_2 = self._allocate_api_tokens(bt1, count=3, repo=repo, user=other_user)
        assert AllocatedRefreshToken.objects.count() == 11
        token_id = token_ids_user_2[1]
        # Fail to revoke other user's tokens.
        response = client.delete(f"/api/v1/tokens/{token_id}/")
        assert response.status_code == 404
        token = AllocatedRefreshToken.objects.get(id=token_id)
        assert token.is_active is True
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert AllocatedRefreshToken.objects.filter(_token_state=AllocatedRefreshToken.State.ACTIVE.value).count() == 10

        # Non existent token
        response = client.delete("/api/v1/tokens/seinfeld/")
        assert response.status_code == 404
        assert AllocatedRefreshToken.objects.filter(_token_state=AllocatedRefreshToken.State.ACTIVE.value).count() == 10

    @pytest.mark.parametrize("state", [AccessTokenState.EXPIRED, AccessTokenState.REVOKED])
    def test_revoke_inactive(
        self, client: APIClient, customer: Customer, user: ToolchainUser, state: AccessTokenState
    ) -> None:
        repo = Repo.create("cookie", customer, "Look to the cookie")
        bt1 = datetime.datetime(2020, 6, 13, 18, tzinfo=datetime.timezone.utc)
        token_ids = self._allocate_api_tokens(bt1, count=6, repo=repo, user=user)
        token_id = token_ids[-2]
        AllocatedRefreshToken.objects.filter(id=token_id).update(_token_state=state.value)
        assert AllocatedRefreshToken.objects.filter(_token_state=AllocatedRefreshToken.State.ACTIVE.value).count() == 5

        response = client.delete(f"/api/v1/tokens/{token_id}/")
        assert response.status_code == 400
        assert response.json() == {"token": ["Token is not active."]}
        assert AllocatedRefreshToken.objects.filter(_token_state=AllocatedRefreshToken.State.ACTIVE.value).count() == 5

    def test_set_description(self, client: APIClient, customer: Customer, user: ToolchainUser) -> None:
        repo = Repo.create("cookie", customer, "Look to the cookie")
        bt1 = datetime.datetime(2020, 5, 13, 4, 45, 19, tzinfo=datetime.timezone.utc)
        self._allocate_ui_tokens(user)
        token_ids = self._allocate_api_tokens(bt1, count=6, repo=repo, user=user)
        token_id = token_ids[4]
        response = client.patch(
            f"/api/v1/tokens/{token_id}/", data={"description": "     How come people don’t have dip for dinner    "}
        )
        assert response.status_code == 201
        assert response.json() == {"description": "How come people don’t have dip for dinner"}
        token = AllocatedRefreshToken.objects.get(id=token_id)
        assert token.is_active is True
        assert token.description == "How come people don’t have dip for dinner"

    def test_set_description_404(
        self, client: APIClient, customer: Customer, user: ToolchainUser, other_user: ToolchainUser
    ) -> None:
        repo = Repo.create("cookie", customer, "Look to the cookie")
        bt1 = datetime.datetime(2020, 5, 13, 4, 45, 19, tzinfo=datetime.timezone.utc)
        self._allocate_ui_tokens(user)
        token_ids = self._allocate_api_tokens(bt1, count=6, repo=repo, user=other_user)
        token_id = token_ids[4]
        response = client.patch(f"/api/v1/tokens/{token_id}/", data={"description": "dip for dinner"})
        assert response.status_code == 404
        response = client.patch("/api/v1/tokens/festivus/", data={"description": "How come"})
        assert response.status_code == 404

    def test_set_description_invalid(self, client: APIClient, customer: Customer, user: ToolchainUser) -> None:
        repo = Repo.create("cookie", customer, "Look to the cookie")
        bt1 = datetime.datetime(2020, 5, 13, 4, 45, 19, tzinfo=datetime.timezone.utc)
        self._allocate_ui_tokens(user)
        token_ids = self._allocate_api_tokens(bt1, count=6, repo=repo, user=user)
        token_id = token_ids[4]
        response = client.patch(
            f"/api/v1/tokens/{token_id}/", data={"desc": "dip for dinner", "description": "festivus"}
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"__all__": [{"message": "Got unexpected fields: desc", "code": "unexpected"}]}
        }

        response = client.patch(f"/api/v1/tokens/{token_id}/")
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"description": [{"message": "This field is required.", "code": "required"}]}
        }

        response = client.patch(f"/api/v1/tokens/{token_id}/", data={"desc": "dip for dinner"})
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "description": [{"message": "This field is required.", "code": "required"}],
                "__all__": [{"message": "Got unexpected fields: desc", "code": "unexpected"}],
            }
        }

        response = client.patch(f"/api/v1/tokens/{token_id}/", data={"description": ""})
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"description": [{"message": "This field is required.", "code": "required"}]}
        }

        response = client.patch(f"/api/v1/tokens/{token_id}/", data={"description": "    "})
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"description": [{"message": "This field is required.", "code": "required"}]}
        }
        response = client.patch(f"/api/v1/tokens/{token_id}/", data={"description": "   x "})
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "description": [
                    {"message": "Ensure this value has at least 2 characters (it has 1).", "code": "min_length"}
                ]
            }
        }
        response = client.patch(f"/api/v1/tokens/{token_id}/", data={"description": "jerry seinfeld-" * 40})
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "description": [
                    {"message": "Ensure this value has at most 250 characters (it has 600).", "code": "max_length"}
                ]
            }
        }


class TestCustomerView(BaseViewsTest):
    def _add_repos(self, customer: Customer) -> tuple[Repo, ...]:
        customer_2 = Customer.create(slug="newman", name="Hello Newman")
        r1 = Repo.create("cookie", customer, "Look to the cookie")
        r2 = Repo.create("mailbox", customer, "Mail never stops")
        Repo.create("submarine", customer_2, "Turn your key")
        r3 = Repo.create("buzzer", customer, "strongbox")
        return r1, r2, r3

    def test_get_customer_github_as_user(self, httpx_mock, client, user: ToolchainUser, customer: Customer) -> None:
        add_get_install_info_response(httpx_mock, customer.id, with_configure_link=True)
        self._create_uac(customer, user, is_admin=False)
        repo_1, repo_2, repo_3 = self._add_repos(customer)
        repo_1.deactivate()
        response = client.get("/api/v1/customers/acmeid/")
        assert response.status_code == 200
        assert response.json() == {
            "customer": {
                "id": customer.id,
                "slug": "acmeid",
                "name": "acme",
                "logo_url": "https://festivus.com/pole",
                "scm": "github",
                "customer_link": "https://github.com/acmeid/",
            },
            "metadata": {
                "configure_link": "https://github.com/organizations/toolchainlabs/settings/installations/10322049",
                "install_link": "https://github.com/apps/toolchain-dev/installations/new",
            },
            "repos": [
                {
                    "id": repo_3.id,
                    "name": "strongbox",
                    "slug": "buzzer",
                    "is_active": True,
                    "repo_link": "https://github.com/acmeid/buzzer",
                    "scm": "github",
                },
                {
                    "id": repo_2.id,
                    "name": "Mail never stops",
                    "slug": "mailbox",
                    "is_active": True,
                    "repo_link": "https://github.com/acmeid/mailbox",
                    "scm": "github",
                },
            ],
            "user": {"role": "user", "is_admin": False},
        }

    def test_get_customer_github_as_org_admin(
        self, httpx_mock, client, user: ToolchainUser, customer: Customer
    ) -> None:
        add_get_install_info_response(httpx_mock, customer.id, with_configure_link=True)
        self._create_uac(customer, user, is_admin=True)
        repo_1, repo_2, repo_3 = self._add_repos(customer)
        repo_3.deactivate()
        response = client.get("/api/v1/customers/acmeid/")
        assert response.status_code == 200
        assert response.json() == {
            "customer": {
                "id": customer.id,
                "slug": "acmeid",
                "name": "acme",
                "logo_url": "https://festivus.com/pole",
                "scm": "github",
                "customer_link": "https://github.com/acmeid/",
                "billing": "/api/v1/customers/acmeid/billing/",
            },
            "metadata": {
                "configure_link": "https://github.com/organizations/toolchainlabs/settings/installations/10322049",
                "install_link": "https://github.com/apps/toolchain-dev/installations/new",
            },
            "repos": [
                {
                    "id": repo_1.id,
                    "name": "Look to the cookie",
                    "slug": "cookie",
                    "is_active": True,
                    "repo_link": "https://github.com/acmeid/cookie",
                    "scm": "github",
                },
                {
                    "id": repo_2.id,
                    "name": "Mail never stops",
                    "slug": "mailbox",
                    "is_active": True,
                    "repo_link": "https://github.com/acmeid/mailbox",
                    "scm": "github",
                },
                {
                    "id": repo_3.id,
                    "name": "strongbox",
                    "slug": "buzzer",
                    "is_active": False,
                    "repo_link": "https://github.com/acmeid/buzzer",
                    "scm": "github",
                },
            ],
            "user": {"role": "org_admin", "is_admin": True},
        }

    def test_get_customer_bitbucket_as_user(self, client, user: ToolchainUser, bitbucket_customer: Customer) -> None:
        self._create_uac(bitbucket_customer, user, is_admin=False)
        repo = Repo.create("submarine", bitbucket_customer, "Turn your key")
        response = client.get("/api/v1/customers/seinfeld/")
        assert response.status_code == 200
        assert response.json() == {
            "customer": {
                "id": bitbucket_customer.id,
                "slug": "seinfeld",
                "name": "Jerry Seinfeld",
                "logo_url": "https://nbc.com/toms",
                "scm": "bitbucket",
                "customer_link": "https://bitbucket.org/seinfeld/",
            },
            "metadata": {},
            "repos": [
                {
                    "id": repo.id,
                    "name": "Turn your key",
                    "slug": "submarine",
                    "is_active": True,
                    "repo_link": "https://bitbucket.org/seinfeld/submarine",
                    "scm": "bitbucket",
                }
            ],
            "user": {"role": "user", "is_admin": False},
        }

    def test_get_customer_bitbucket_as_org_admin(
        self, client, user: ToolchainUser, bitbucket_customer: Customer
    ) -> None:
        self._create_uac(bitbucket_customer, user, is_admin=True)
        response = client.get("/api/v1/customers/seinfeld/")
        assert response.status_code == 200
        assert response.json() == {
            "customer": {
                "id": bitbucket_customer.id,
                "slug": "seinfeld",
                "name": "Jerry Seinfeld",
                "logo_url": "https://nbc.com/toms",
                "scm": "bitbucket",
                "customer_link": "https://bitbucket.org/seinfeld/",
                "billing": "/api/v1/customers/seinfeld/billing/",
            },
            "metadata": {},
            "repos": [],
            "user": {"role": "org_admin", "is_admin": True},
        }

    @pytest.mark.parametrize("is_admin", [True, False])
    def test_get_customer_inactive(self, client, user: ToolchainUser, customer: Customer, is_admin: bool) -> None:
        self._create_uac(customer, user, is_admin=is_admin)
        customer.deactivate()
        response = client.get("/api/v1/customers/acmeid/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    @pytest.mark.parametrize("is_admin", [True, False])
    def test_get_customer_unknown(self, client, user: ToolchainUser, customer: Customer, is_admin: bool) -> None:
        self._create_uac(customer, user, is_admin=is_admin)
        response = client.get("/api/v1/customers/kramer/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_customer_no_user_access(self, client, user: ToolchainUser) -> None:
        Customer.create(slug="jerry", name="Jerry Seinfeld")
        response = client.get("/api/v1/customers/jerry/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_update_customer_name(self, client: APIClient, user: ToolchainUser, customer: Customer) -> None:
        self._create_uac(customer, user, is_admin=True)
        assert customer.name == "acme"
        response = client.patch("/api/v1/customers/acmeid/", data={"name": "Festivus for the rest of us"})
        assert response.status_code == 201
        updated_customer = Customer.objects.get(id=customer.id)
        assert updated_customer.name == "Festivus for the rest of us"

    def test_update_customer_name_not_org_admin(self, client: APIClient, customer: Customer) -> None:
        assert customer.name == "acme"
        response = client.patch("/api/v1/customers/acmeid/", data={"name": "Festivus for the rest of us"})
        assert response.status_code == 403
        assert Customer.objects.get(id=customer.id).name == customer.name == "acme"

    @pytest.mark.parametrize(
        ("invalid_name", "error_msg", "error_code"),
        [
            ("", "This field is required.", "required"),
            ("  ", "This field is required.", "required"),
            ("jerry!", "Only English letters, numbers, dot, comma, spaces and dashes are allowed.", "invalid"),
            (
                "no _soup for you",
                "Only English letters, numbers, dot, comma, spaces and dashes are allowed.",
                "invalid",
            ),
            ("dave" * 40, "Ensure this value has at most 128 characters (it has 160).", "max_length"),
            ("F", "Ensure this value has at least 2 characters (it has 1).", "min_length"),
        ],
    )
    def test_update_customer_name_invalid_name(
        self,
        client: APIClient,
        user: ToolchainUser,
        customer: Customer,
        invalid_name: str,
        error_msg: str,
        error_code: str,
    ) -> None:
        self._create_uac(customer, user, is_admin=True)
        assert customer.name == "acme"
        response = client.patch("/api/v1/customers/acmeid/", data={"name": invalid_name})
        assert response.status_code == 400
        assert response.json() == {"errors": {"name": [{"message": error_msg, "code": error_code}]}}
        assert Customer.objects.get(id=customer.id).name == customer.name == "acme"


class TestCustomerRepoView(BaseViewsTest):
    def _create_repos(self, customer, prefix: str, count: int):
        for i in range(count):
            Repo.create(slug=f"repo_{prefix}_{i+1}", customer=customer, name=f"Test repo #{i+1}")

    def test_deactivate_repo(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        self._create_uac(customer, user, is_admin=True)
        assert repo_1.is_active is True
        response = client.delete("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 201
        assert response.json() == {
            "repo": {
                "id": repo_1.id,
                "name": "Look to the cookie",
                "slug": "cookie",
                "is_active": False,
                "repo_link": "https://github.com/acmeid/cookie",
                "scm": "github",
            }
        }
        assert Repo.objects.get(id=repo_1.id).is_active is False

    def test_deactivate_inactive_repo(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        self._create_uac(customer, user, is_admin=True)
        repo_1.deactivate()
        response = client.delete("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 200
        assert response.json() == {
            "repo": {
                "id": repo_1.id,
                "name": "Look to the cookie",
                "slug": "cookie",
                "is_active": False,
                "repo_link": "https://github.com/acmeid/cookie",
                "scm": "github",
            }
        }
        assert Repo.objects.get(id=repo_1.id).is_active is False

    def test_deactivate_repo_not_admin(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        self._create_uac(customer, user, is_admin=False)
        assert repo_1.is_active is True
        response = client.delete("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to perform this action."}
        assert Repo.objects.get(id=repo_1.id).is_active is True

    def test_activate_repo(self, client, user: ToolchainUser, customer: Customer) -> None:
        self._create_uac(customer, user, is_admin=True)
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        repo_1.deactivate()
        assert repo_1.is_active is False
        response = client.post("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 201
        assert response.json() == {
            "repo": {
                "id": repo_1.id,
                "name": "Look to the cookie",
                "slug": "cookie",
                "is_active": True,
                "repo_link": "https://github.com/acmeid/cookie",
                "scm": "github",
            }
        }
        assert Repo.objects.get(id=repo_1.id).is_active is True

    def test_activate_repo_already_active(self, client, user: ToolchainUser, customer: Customer) -> None:
        self._create_uac(customer, user, is_admin=True)
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        response = client.post("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 200
        assert response.json() == {
            "repo": {
                "id": repo_1.id,
                "name": "Look to the cookie",
                "slug": "cookie",
                "is_active": True,
                "repo_link": "https://github.com/acmeid/cookie",
                "scm": "github",
            }
        }
        assert Repo.objects.get(id=repo_1.id).is_active is True

    def test_activate_repo_max_reached(self, client, user: ToolchainUser, customer: Customer) -> None:
        self._create_uac(customer, user, is_admin=True)
        repo = Repo.create("cookie", customer, "Look to the cookie")
        repo.deactivate()
        self._create_repos(customer, "newman", count=Repo.MAX_CUSTOMER_REPOS)

        response = client.post("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 400
        assert response.json() == {"detail": "Max active repos customer reached."}
        assert Repo.objects.get(id=repo.id).is_active is False

    def test_activate_repo_not_admin(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        repo_1.deactivate()
        self._create_uac(customer, user, is_admin=False)
        assert repo_1.is_active is False
        response = client.post("/api/v1/customers/acmeid/repos/cookie/")
        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to perform this action."}
        assert Repo.objects.get(id=repo_1.id).is_active is False

    def test_activate_unknown_repo(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        repo_1.deactivate()
        self._create_uac(customer, user, is_admin=True)
        assert repo_1.is_active is False
        response = client.post("/api/v1/customers/acmeid/repos/newman/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}
        assert Repo.objects.get(id=repo_1.id).is_active is False

    def test_deactivate_unknown_repo(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        self._create_uac(customer, user, is_admin=True)
        response = client.delete("/api/v1/customers/acmeid/repos/newman/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}
        assert Repo.objects.get(id=repo_1.id).is_active is True


class TestCustomerBillingView(BaseViewsTest):
    def test_create_portal_session_as_admin(self, httpx_mock, client, user: ToolchainUser, customer: Customer) -> None:
        self._create_uac(customer, user, is_admin=True)
        add_create_portal_session_response(httpx_mock, customer_id=customer.id)
        response = client.post("/api/v1/customers/acmeid/billing/", HTTP_REFERER="http://testserver/jerry")
        assert response.status_code == 201
        assert response.json() == {"session_url": "https://newman-billing.com/session/no-soup-for-you"}
        assert_create_portal_session_request(
            httpx_mock.get_request(), customer_id=customer.id, return_url="http://testserver/jerry"
        )

    def test_create_portal_session_non_admin(self, client, user: ToolchainUser, customer: Customer, caplog) -> None:
        self._create_uac(customer, user, is_admin=False)
        response = client.post("/api/v1/customers/acmeid/billing/", HTTP_REFERER="http://testserver/jerry")
        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to perform this action."}
        assert_messages(caplog, "User kramer is not org admin. role: user")

    def test_create_portal_session_no_stripe_customer(
        self, httpx_mock, client, user: ToolchainUser, customer: Customer, caplog
    ) -> None:
        self._create_uac(customer, user, is_admin=True)
        add_create_portal_session_response(httpx_mock, customer_id=customer.id, session_url=None)
        response = client.post("/api/v1/customers/acmeid/billing/", HTTP_REFERER="http://testserver/jerry")
        assert response.status_code == 404
        assert response.json() == {
            "detail": "Access to plan management UI is not available yet. Try again in a few minutes."
        }
        assert_create_portal_session_request(
            httpx_mock.get_request(), customer_id=customer.id, return_url="http://testserver/jerry"
        )
        assert_messages(caplog, "Can't create portal session for customer")

    def test_create_portal_session_bad_referrer(self, client, user: ToolchainUser, customer: Customer, caplog) -> None:
        self._create_uac(customer, user, is_admin=True)
        response = client.post("/api/v1/customers/acmeid/billing/", HTTP_REFERER="jerry")
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid value for `referer` header"}
        assert_messages(caplog, "Invalid value for `referer` header")

    def test_create_portal_session_unauthenticated(self) -> None:
        response = APIClient().post("/api/v1/customers/acmeid/billing/", HTTP_REFERER="http://testserver/jerry")
        assert response.status_code == 403
        assert response.json() == {"detail": "Authentication credentials were not provided."}


class TestCustomerPlanView(BaseViewsTest):
    def test_get_starter_plan(self, httpx_mock, client, user: ToolchainUser, customer: Customer) -> None:
        # This test will break in April 2026, but I don't expect it to be here, unmodified until that date.
        add_get_plan_and_usage_response(
            httpx_mock, customer_id=customer.id, plan_name="Starter Plan", trial_end_date="2026-04-29"
        )
        response = client.get("/api/v1/customers/acmeid/plan/")
        assert response.status_code == 200
        assert response.json() == {
            "plan": {
                "name": "Starter Plan",
                "price": "no soup for you",
                "has_trail_ended": False,
                "trial_end": "2026-04-29",
                "description": "For small teams getting started with Pants",
                "resources": [
                    "Teams of up to 10 developers",
                    "Up to 100 GB cache storage",
                    "Up to 500 GB outbound data transfer per month",
                    "Community support",
                    "Free to try for 30 days",
                ],
            },
            "usage": {"bandwidth": {"outbound": "111.0 MB", "inbound": "322.0 MB"}},
        }

    def test_get_enterprise_plan(self, httpx_mock, client, user: ToolchainUser, customer: Customer) -> None:
        add_get_plan_and_usage_response(
            httpx_mock, customer_id=customer.id, plan_name="Enterprise Plan", trial_end_date="2022-10-10"
        )
        response = client.get("/api/v1/customers/acmeid/plan/")
        assert response.status_code == 200
        assert response.json() == {
            "plan": {
                "name": "Enterprise Plan",
                "price": "no soup for you",
                "has_trail_ended": True,
                "trial_end": "2022-10-10",
                "description": "For growing teams of all sizes",
                "resources": [
                    "Teams of any size",
                    "Cache storage as needed",
                    "Data transfer as needed",
                    "Enterprise support",
                ],
            },
            "usage": {"bandwidth": {"outbound": "111.0 MB", "inbound": "322.0 MB"}},
        }

    def test_get_no_plan_with_usage(self, httpx_mock, client, user: ToolchainUser, customer: Customer) -> None:
        add_get_plan_and_usage_response(httpx_mock, customer_id=customer.id, with_plan=False)
        response = client.get("/api/v1/customers/acmeid/plan/")
        assert response.status_code == 200
        assert response.json() == {
            "plan": {
                "name": "N/A",
                "price": "N/A",
                "description": "For small teams getting started with Pants",
                "resources": [
                    "Teams of up to 10 developers",
                    "Up to 100 GB cache storage",
                    "Up to 500 GB outbound data transfer per month",
                    "Community support",
                    "Free to try for 30 days",
                ],
            },
            "usage": {"bandwidth": {"outbound": "111.0 MB", "inbound": "322.0 MB"}},
        }

    def test_get_no_plan_no_usage(self, httpx_mock, client, user: ToolchainUser, customer: Customer) -> None:
        add_get_plan_and_usage_response(httpx_mock, customer_id=customer.id, with_plan=False, with_usage=False)
        response = client.get("/api/v1/customers/acmeid/plan/")
        assert response.status_code == 200
        assert response.json() == {
            "plan": {
                "name": "N/A",
                "price": "N/A",
                "description": "For small teams getting started with Pants",
                "resources": [
                    "Teams of up to 10 developers",
                    "Up to 100 GB cache storage",
                    "Up to 500 GB outbound data transfer per month",
                    "Community support",
                    "Free to try for 30 days",
                ],
            },
            "usage": {"bandwidth": {"outbound": None, "inbound": None}},
        }


class TestCustomerRemoteWorkerTokensView(BaseViewsTest):
    def _create_token(self, customer: Customer, description: str | None = None) -> RemoteExecWorkerToken:
        return RemoteExecWorkerToken.create(
            customer_id=customer.id,
            user_api_id="constanza",
            customer_slug=customer.slug,
            description=description or f"Festivus {customer.name}",
        )

    def test_customer_options_allowed(self, client, customer: Customer) -> None:
        response = client.options("/api/v1/customers/acmeid/workers/tokens/")
        assert response.status_code == 200
        assert response.json() == {"allowed": True}

    def test_customer_options_not_allowed(self, client, caplog, user: ToolchainUser) -> None:
        customer = Customer.create(slug="costanza", name="Gerorge Costanza")
        customer.add_user(user)
        response = client.options("/api/v1/customers/costanza/workers/tokens/")
        assert response.status_code == 200
        assert response.json() == {"allowed": False}
        assert_messages(caplog, "Customer: costanza not allowed to use remote worker tokens.")

    def test_customer_options_oss_not_admin_not_allowed(self, other_user: ToolchainUser, caplog) -> None:
        client = self._get_client(other_user)
        customer = Customer.create(slug="davola", name="Joe Davola", customer_type=Customer.Type.OPEN_SOURCE)
        customer.add_user(other_user)
        response = client.options("/api/v1/customers/davola/workers/tokens/")
        assert response.status_code == 200
        assert response.json() == {"allowed": False}
        assert_messages(caplog, "Customer: davola is OSS, only org admin can access remote worker tokens.")

    def test_customer_options_oss_admin(self, other_user: ToolchainUser, caplog) -> None:
        client = self._get_client(other_user)
        customer = Customer.create(slug="davola", name="Joe Davola", customer_type=Customer.Type.OPEN_SOURCE)
        customer.add_user(other_user)
        self._create_uac(customer, other_user, is_admin=True)
        response = client.options("/api/v1/customers/davola/workers/tokens/")
        assert response.status_code == 200
        assert response.json() == {"allowed": True}

    def test_get_for_customer_not_allowed(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="costanza", name="Gerorge Costanza")
        customer.add_user(user)
        response = client.get("/api/v1/customers/costanza/workers/tokens/")
        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to perform this action."}

    def test_get_for_customer_no_tokens(self, client, customer: Customer) -> None:
        response = client.get("/api/v1/customers/acmeid/workers/tokens/")
        assert response.status_code == 200
        assert response.json() == {"tokens": []}

    def test_get_for_customer(self, client, customer: Customer) -> None:
        with freeze_time(utcnow() - datetime.timedelta(minutes=30)):
            token_1 = self._create_token(customer)
        with freeze_time(utcnow() - datetime.timedelta(minutes=13)):
            token_2 = self._create_token(customer, description="soup")
        token_3 = self._create_token(customer)
        token_2.deactivate()
        response = client.get("/api/v1/customers/acmeid/workers/tokens/")
        assert response.status_code == 200
        assert response.json() == {
            "tokens": [
                {
                    "created_at": token_3.created_at.isoformat(),
                    "state": "active",
                    "description": "Festivus acme",
                    "token": token_3.token,
                    "id": token_3.id,
                },
                {
                    "created_at": token_2.created_at.isoformat(),
                    "state": "inactive",
                    "description": "soup",
                    "id": token_2.id,
                },
                {
                    "created_at": token_1.created_at.isoformat(),
                    "state": "active",
                    "description": "Festivus acme",
                    "token": token_1.token,
                    "id": token_1.id,
                },
            ]
        }

    def test_get_for_custome_invalid_user(self, client, other_customer: Customer) -> None:
        response = client.get("/api/v1/customers/othercustomer/workers/tokens/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_create_remote_worker_token_form_encoding(self, client, customer: Customer) -> None:
        assert RemoteExecWorkerToken.objects.count() == 0
        response = client.post("/api/v1/customers/acmeid/workers/tokens/", data={"description": "Del Boca Vista"})
        assert response.status_code == 200
        assert RemoteExecWorkerToken.objects.count() == 1
        token = RemoteExecWorkerToken.objects.first()
        assert response.json() == {
            "token": {
                "created_at": token.created_at.isoformat(),
                "state": "active",
                "description": "Del Boca Vista",
                "token": token.token,
                "id": token.id,
            }
        }

    def test_create_remote_worker_token_json_encoding(self, client, customer: Customer) -> None:
        assert RemoteExecWorkerToken.objects.count() == 0
        response = client.post(
            "/api/v1/customers/acmeid/workers/tokens/",
            content_type="application/json",
            data=json.dumps({"description": "Del Boca Vista"}),
        )
        assert response.status_code == 200
        assert RemoteExecWorkerToken.objects.count() == 1
        token = RemoteExecWorkerToken.objects.first()
        assert response.json() == {
            "token": {
                "created_at": token.created_at.isoformat(),
                "state": "active",
                "description": "Del Boca Vista",
                "token": token.token,
                "id": token.id,
            }
        }

    def test_delete_token(self, client, customer: Customer) -> None:
        token_id = self._create_token(customer).id
        assert RemoteExecWorkerToken.objects.count() == 1
        response = client.delete(f"/api/v1/customers/acmeid/workers/tokens/{token_id}/")
        assert response.status_code == 200
        assert RemoteExecWorkerToken.objects.count() == 1
        token = RemoteExecWorkerToken.objects.first()
        assert token.state == RemoteExecWorkerToken.State.INACTIVE
        assert response.json() == {
            "token": {
                "created_at": token.created_at.isoformat(),
                "state": "inactive",
                "description": "Festivus acme",
                "id": token.id,
            }
        }
