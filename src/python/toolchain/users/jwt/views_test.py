# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from urllib.parse import parse_qsl, urlparse

import pytest
from dateutil.parser import parse
from django.conf import settings
from freezegun import freeze_time
from jose import jws
from rest_framework.test import APIClient

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.claims import UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.models import AccessTokenUsage, AllocatedRefreshToken, Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user, create_staff
from toolchain.github_integration.client.repo_clients_test import (
    add_ci_resolve_error_response_for_repo,
    add_ci_resolve_response_for_repo,
)
from toolchain.users.jwt.utils import check_refresh_token, generate_refresh_token, get_or_create_refresh_token_for_ui
from toolchain.users.models import (
    AccessTokenExchangeCode,
    GithubRepoConfig,
    RestrictedAccessToken,
    UserCustomerAccessConfig,
)
from toolchain.users.ui.views_test import assert_refresh_token_cookie
from toolchain.util.test.util import convert_headers_to_wsgi


def _get_access_token_key_id():
    return settings.JWT_AUTH_KEY_DATA.get_current_access_token_key().key_id


def _get_client_with_access_token_auth_header(user: ToolchainUser) -> APIClient:
    claims = UserClaims(
        user_api_id=user.api_id,
        username=user.username,
        audience=AccessTokenAudience.FRONTEND_API,
        token_type=AccessTokenType.ACCESS_TOKEN,
        token_id=None,
    )
    headers = create_internal_auth_headers(user, claims=claims.as_json_dict(), impersonation=None)
    return APIClient(**convert_headers_to_wsgi(headers))


def _get_client_with_refresh_token_auth_header(user: ToolchainUser, repo: Repo | None = None) -> APIClient:
    now = utcnow()
    expires_at = now + datetime.timedelta(minutes=5)
    if repo:
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.pk,
            customer=repo.customer,
            expiration_time=expires_at,
            audience=AccessTokenAudience.DEPENDENCY_API,
            description="no soup for you",
        )
    else:
        token_str, _ = get_or_create_refresh_token_for_ui(user=user)

    return APIClient(HTTP_AUTHORIZATION=f"Bearer {token_str}")


@pytest.mark.django_db()
class TestAccessTokenAuthView:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="yada", name="Yada Yada")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def user2(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="kramer", email="kramer@jerry.com")
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.DEPENDENCY_API,
            is_org_admin=False,
        )
        customer.add_user(user)
        return user

    @pytest.fixture()
    def user2_client(self, request, user2: ToolchainUser) -> APIClient:
        return _get_client_with_access_token_auth_header(user2)

    @pytest.fixture()
    def user_client(self, request, user: ToolchainUser) -> APIClient:
        return _get_client_with_access_token_auth_header(user)

    def _assert_exchange_code(self, repo, user) -> str:
        assert AccessTokenExchangeCode.objects.count() == 1
        exchange_code = AccessTokenExchangeCode.objects.first()
        assert exchange_code.created_at.timestamp() == pytest.approx(utcnow().timestamp())
        assert exchange_code.user_api_id == user.api_id
        assert exchange_code.repo_id == repo.pk
        assert exchange_code.is_available is True
        return exchange_code.code

    @pytest.mark.parametrize(
        "redirect_uri", ["http://///////////", "no soup for you", None, "http://jerry.com:99383833", "http://jerry.com"]
    )
    def test_invalid_redirect_uri(self, user_client: APIClient, user: ToolchainUser, redirect_uri: str) -> None:
        assert AccessTokenExchangeCode.objects.count() == 0
        params = {"repo": "pez"}
        if redirect_uri is not None:
            params["redirect_uri"] = redirect_uri
        response = user_client.get("/api/v1/token/auth/", data=params)
        assert response.status_code == 400
        assert response.template_name == "users/error.html"
        assert response.context_data["error_message"] == "Invalid params"
        assert "Invalid params" in response.content.decode()

    def test_user_without_repos(self, user_client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="frank", name="Feats of strength")
        Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        assert AccessTokenExchangeCode.objects.count() == 0
        redirect_uri = "http://localhost:8821/the/airconditioner/?state=puffyshirt"
        response = user_client.get("/api/v1/token/auth/", data={"repo": "pez", "redirect_uri": redirect_uri})
        assert response.status_code == 302
        assert AccessTokenExchangeCode.objects.count() == 0
        query_params = dict(parse_qsl(urlparse(response.url).query))
        assert query_params == {"error": "Invalid repo for user", "state": "puffyshirt"}
        assert response.url.startswith("http://localhost:8821/the/airconditioner/?")

    def test_get_token_exchange_code_repo_slug(
        self, user2_client: APIClient, user2: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        assert AccessTokenExchangeCode.objects.count() == 0
        redirect_uri = "http://localhost:8821/the/airconditioner/?state=puffyshirt"
        response = user2_client.get("/api/v1/token/auth/", data={"repo": "pez", "redirect_uri": redirect_uri})
        assert response.status_code == 302
        query_params = dict(parse_qsl(urlparse(response.url).query))
        assert response.url.startswith("http://localhost:8821/the/airconditioner/?")
        code = self._assert_exchange_code(repo, user2)
        assert query_params == {"state": "puffyshirt", "code": code}

    def test_get_token_exchange_code_repo_fn(
        self, user2_client: APIClient, user2: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        assert AccessTokenExchangeCode.objects.count() == 0
        redirect_uri = "http://localhost:8821/the/airconditioner/?state=puffyshirt"
        response = user2_client.get("/api/v1/token/auth/", data={"repo": "yada/pez", "redirect_uri": redirect_uri})
        assert response.status_code == 302
        query_params = dict(parse_qsl(urlparse(response.url).query))
        assert response.url.startswith("http://localhost:8821/the/airconditioner/?")
        code = self._assert_exchange_code(repo, user2)
        assert query_params == {"state": "puffyshirt", "code": code}

    def test_get_token_exchange_code_headless_repo_slug(
        self, user2_client: APIClient, user2: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="yankees", customer=customer, name="Yankees Stadium")
        assert AccessTokenExchangeCode.objects.count() == 0
        response = user2_client.get("/api/v1/token/auth/", data={"repo": "yankees", "headless": "1"})
        assert response.status_code == 201
        assert response.template_name == "users/headless_new.html"
        code = self._assert_exchange_code(repo, user2)
        assert response.context_data["access_code_data"] == code
        assert code in response.content.decode()

    def test_get_token_exchange_code_headless_repo_fn(
        self, user2_client: APIClient, user2: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="yankees", customer=customer, name="Yankees Stadium")
        assert AccessTokenExchangeCode.objects.count() == 0
        response = user2_client.get("/api/v1/token/auth/", data={"repo": "yada/yankees", "headless": "1"})
        assert response.status_code == 201
        assert response.template_name == "users/headless_new.html"
        code = self._assert_exchange_code(repo, user2)
        assert response.context_data["access_code_data"] == code
        assert code in response.content.decode()

    def test_get_token_exchange_code_headless_not_authenticated_repo_slug(
        self, client: APIClient, customer: Customer
    ) -> None:
        Repo.create(slug="yankees", customer=customer, name="Yankees Stadium")
        assert AccessTokenExchangeCode.objects.count() == 0
        response = client.get("/api/v1/token/auth/", data={"repo": "yankees", "headless": "1"})
        assert response.status_code == 302
        assert (
            response.url
            == "http://localhost:9500/auth/login/?next=http%3A//testserver/api/v1/token/auth/%3Frepo%3Dyankees%26headless%3D1"
        )
        assert AccessTokenExchangeCode.objects.count() == 0

    def test_get_token_exchange_code_headless_not_authenticated_repo_fn(
        self, client: APIClient, customer: Customer
    ) -> None:
        Repo.create(slug="yankees", customer=customer, name="Yankees Stadium")
        assert AccessTokenExchangeCode.objects.count() == 0
        response = client.get("/api/v1/token/auth/", data={"repo": "yada/yankees", "headless": "1"})
        assert response.status_code == 302
        assert (
            response.url
            == "http://localhost:9500/auth/login/?next=http%3A//testserver/api/v1/token/auth/%3Frepo%3Dyada%252Fyankees%26headless%3D1"
        )
        assert AccessTokenExchangeCode.objects.count() == 0

    def test_redirects_on_token_acquire(self, client) -> None:
        response = client.get(
            "/api/v1/token/auth/?redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Ftoken-callback%2F&state=bob&repo=toolchainlabs%2Ftoolchain"
        )
        assert response.status_code == 302
        assert response.status_code == 302
        top_query_params = dict(parse_qsl(urlparse(response.url).query))
        assert len(top_query_params) == 1
        assert "next" in top_query_params
        next_url = urlparse(top_query_params["next"])
        assert next_url.path == "/api/v1/token/auth/"
        assert dict(parse_qsl(next_url.query)) == {
            "redirect_uri": "http://localhost:8001/token-callback/",
            "state": "bob",
            "repo": "toolchainlabs/toolchain",
        }
        assert (
            response.url
            == "http://localhost:9500/auth/login/?next=http%3A//testserver/api/v1/token/auth/%3Fredirect_uri%3Dhttp%253A%252F%252Flocalhost%253A8001%252Ftoken-callback%252F%26state%3Dbob%26repo%3Dtoolchainlabs%252Ftoolchain"
        )
        assert AccessTokenExchangeCode.objects.count() == 0


@pytest.mark.django_db()
class TestAccessTokenExchangeView:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="yada", name="Yada Yada")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="cosmo", email="kramer@bob.com")
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.DEPENDENCY_API,
            is_org_admin=False,
        )
        return user

    @pytest.fixture()
    def staff_user(self, customer: Customer) -> ToolchainUser:
        user = create_staff(username="jerry", email="jerry@bob.com")
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.DEPENDENCY_API
            | AccessTokenAudience.IMPERSONATE,
            is_org_admin=True,
        )
        return user

    @property
    def current_refresh_token_key_id(self) -> str:
        return settings.JWT_AUTH_KEY_DATA.get_current_refresh_token_key().key_id

    def test_exchange(self, client, customer: Customer, user: ToolchainUser) -> None:
        customer.add_user(user)
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 200
        response_json = response.json()
        now = utcnow()
        access_token = response_json.pop("access_token")
        expiration = parse(response_json.pop("expires_at"))
        assert int(expiration.timestamp()) == pytest.approx(int((now + datetime.timedelta(days=180)).timestamp()))
        assert response_json == {"user": "cosmo", "repo": "gold"}
        claims = json.loads(jws.get_unverified_claims(access_token))
        assert jws.get_unverified_headers(access_token) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_refresh_token_key_id,
        }
        issued_at = claims.pop("iat")
        assert int((expiration - datetime.timedelta(days=180)).timestamp()) == pytest.approx(issued_at, rel=2)
        assert issued_at == pytest.approx(int(utcnow().timestamp()))
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert claims == {
            "jid": token.id,
            "exp": int(expiration.timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense"],
            "username": "cosmo",
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "toolchain_repo": repo.pk,
            "toolchain_customer": customer.pk,
        }
        assert AccessTokenExchangeCode.objects.count() == 1
        token_exchange = AccessTokenExchangeCode.objects.first()
        assert token_exchange.is_available is False
        assert token_exchange.state == AccessTokenExchangeCode.State.USED

    def test_exchange_with_impersonate(self, client, staff_user: ToolchainUser) -> None:
        customer = Customer.create(slug="risk", name="World Domination")
        customer.add_user(staff_user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=staff_user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
            is_org_admin=True,
        )
        repo = Repo.create(slug="swiss", customer=customer, name="Switzerland")
        code = AccessTokenExchangeCode.create_for_user(user=staff_user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code, "allow_impersonation": "1"})
        assert response.status_code == 200
        response_json = response.json()
        now = utcnow()
        access_token = response_json.pop("access_token")
        expiration = parse(response_json.pop("expires_at"))
        assert int(expiration.timestamp()) == pytest.approx(int((now + datetime.timedelta(days=365)).timestamp()))
        assert response_json == {"user": "jerry", "repo": "swiss"}
        claims = json.loads(jws.get_unverified_claims(access_token))
        assert jws.get_unverified_headers(access_token) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_refresh_token_key_id,
        }
        issued_at = claims.pop("iat")
        assert int((expiration - datetime.timedelta(days=365)).timestamp()) == issued_at
        assert issued_at == pytest.approx(int(utcnow().timestamp()))
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert claims == {
            "jid": token.id,
            "exp": int(expiration.timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense", "impersonate"],
            "username": "jerry",
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_user": staff_user.api_id,
            "toolchain_repo": repo.pk,
            "toolchain_customer": customer.pk,
        }
        assert AccessTokenExchangeCode.objects.count() == 1
        token_exchange = AccessTokenExchangeCode.objects.first()
        assert token_exchange.is_available is False
        assert token_exchange.state == AccessTokenExchangeCode.State.USED

    def test_exchange_with_impersonate_not_allowed(self, client, staff_user: ToolchainUser, customer: Customer) -> None:
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=staff_user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API,
            is_org_admin=False,
        )

        customer = Customer.create(slug="risk", name="World Domination")
        customer.add_user(staff_user)
        repo = Repo.create(slug="swiss", customer=customer, name="Switzerland")
        code = AccessTokenExchangeCode.create_for_user(user=staff_user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code, "allow_impersonation": "1"})
        assert response.status_code == 403
        assert response.json() == {"message": "Missing permissions"}
        assert AllocatedRefreshToken.objects.count() == 0
        assert AccessTokenExchangeCode.objects.count() == 1
        token_exchange = AccessTokenExchangeCode.objects.first()
        assert token_exchange.is_available is False
        assert token_exchange.state == AccessTokenExchangeCode.State.USED

    def test_exchange_code_for_token_missing_code_failure(self, client, user: ToolchainUser) -> None:
        response = client.post("/api/v1/token/exchange/", data={"code": "no-soup-for-you"})
        assert response.status_code == 400
        assert response.json() == {"message": "Invalid exchange code"}

    def test_exchange_code_for_token_reuse_code_failure(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        assert AccessTokenExchangeCode.use_code(code) is not None
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 400
        assert response.json() == {"message": "Invalid exchange code"}

    def test_exchange_code_for_token_expired_failure(self, client, user: ToolchainUser) -> None:
        now = utcnow()
        with freeze_time(now - datetime.timedelta(minutes=10)):
            customer = Customer.create(slug="florida", name="del boca vista")
            customer.add_user(user)
            repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
            code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 400
        assert response.json() == {"message": "Invalid exchange code"}

    def test_exchange_code_for_token_inactive_user_failure(
        self, client, user: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        user.deactivate()
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 403
        assert response.json() == {"message": "Invalid user."}

    def test_exchange_code_for_token_invalid_repo_failure(
        self, client, user: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        repo.delete()
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 400
        assert response.json() == {"message": "Repo N/A"}

    def test_exchange_code_for_token_invalid_repo_failure_remove_user_from_customer(
        self, client, user: ToolchainUser, customer: Customer
    ) -> None:
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        customer.users.remove(user)
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 400
        assert response.json() == {"message": "Repo N/A"}

    def test_max_user_access_tokens(self, client, user: ToolchainUser, customer: Customer) -> None:
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        now = utcnow()
        for delta in range(0, AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API]):
            generate_refresh_token(
                user=user,
                repo_pk="independent-george",
                customer=customer,
                expiration_time=now + datetime.timedelta(days=1 + delta),
                audience=AccessTokenAudience.for_pants_client(),
                description="Three squares? You can’t spare three squares?",
            )
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 401

    def test_bad_data_unknown_field(self, client) -> None:
        response = client.post("/api/v1/token/exchange/", data={"movie": "filk"})
        assert response.status_code == 400
        assert response.json() == {
            "message": "* code\n  * This field is required.\n* __all__\n  * Got unexpected fields: movie",
            "errors": {
                "code": [{"message": "This field is required.", "code": "required"}],
                "__all__": [{"message": "Got unexpected fields: movie", "code": "unexpected"}],
            },
        }

    def test_bad_data_empty_code(self, client) -> None:
        response = client.post("/api/v1/token/exchange/", data={"code": ""})
        assert response.status_code == 400
        assert response.json() == {
            "message": "* code\n  * This field is required.",
            "errors": {"code": [{"message": "This field is required.", "code": "required"}]},
        }

    def test_impersonate_not_allowed(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="risk", name="World Domination")
        customer.add_user(user)
        repo = Repo.create(slug="bermuda", customer=customer, name="British")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code, "allow_impersonation": "1"})
        assert response.status_code == 403
        assert response.json() == {"message": "Missing permissions"}

    def test_impersonate_permission_not_granted(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="risk", name="World Domination")
        repo = Repo.create(slug="bermuda", customer=customer, name="British")
        user = create_staff(username="bob", email="bob@sacamano.com")
        customer.add_user(user)
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code, "allow_impersonation": "1"})
        assert response.status_code == 403
        assert response.json() == {"message": "Missing permissions"}

    def test_impersonate_inactive_user(self, client, staff_user: ToolchainUser) -> None:
        customer = Customer.create(slug="risk", name="World Domination")
        customer.add_user(staff_user)
        repo = Repo.create(slug="bermuda", customer=customer, name="British")
        code = AccessTokenExchangeCode.create_for_user(user=staff_user, repo_id=repo.pk)
        staff_user.deactivate()
        response = client.post("/api/v1/token/exchange/", data={"code": code, "allow_impersonation": "1"})
        assert response.status_code == 403
        assert response.json() == {"message": "Invalid user."}

    def test_exchange_token_readonly_user(self, client) -> None:
        customer = Customer.create(slug="yada", name="Yada Yada")
        user = ToolchainUser.create(username="izzy", email="izzy@mandelbaum.com")
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.FRONTEND_API,
            is_org_admin=False,
        )
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code})
        assert response.status_code == 403
        assert response.json() == {"message": "Missing permissions"}

    def test_exchange_with_description(self, client, customer: Customer, user: ToolchainUser) -> None:
        customer.add_user(user)
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post("/api/v1/token/exchange/", data={"code": code, "desc": "He stopped short?"})
        assert response.status_code == 200
        response_json = response.json()
        now = utcnow()
        access_token = response_json.pop("access_token")
        expiration = parse(response_json.pop("expires_at"))
        assert int(expiration.timestamp()) == pytest.approx(int((now + datetime.timedelta(days=180)).timestamp()))
        assert response_json == {"user": "cosmo", "repo": "gold"}
        claims = json.loads(jws.get_unverified_claims(access_token))
        assert jws.get_unverified_headers(access_token) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_refresh_token_key_id,
        }
        issued_at = claims.pop("iat")
        assert int((expiration - datetime.timedelta(days=180)).timestamp()) == pytest.approx(issued_at, rel=2)
        assert issued_at == pytest.approx(int(utcnow().timestamp()))
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert token.description == "He stopped short?"
        assert claims == {
            "jid": token.id,
            "exp": int(expiration.timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense"],
            "username": "cosmo",
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "toolchain_repo": repo.pk,
            "toolchain_customer": customer.pk,
        }
        assert AccessTokenExchangeCode.objects.count() == 1
        token_exchange = AccessTokenExchangeCode.objects.first()
        assert token_exchange.is_available is False
        assert token_exchange.state == AccessTokenExchangeCode.State.USED

    def test_iremote_execution_not_allowed_for_customer(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="risk", name="World Domination")  # not in ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.REMOTE_EXECUTION,
            is_org_admin=False,
        )
        repo = Repo.create(slug="bermuda", customer=customer, name="British")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post(
            "/api/v1/token/exchange/", data={"code": code, "desc": "He stopped short?", "remote_execution": "1"}
        )
        assert response.status_code == 403
        assert response.json() == {"message": "Remote execution permission denided"}

    def test_remote_execution_not_allowed_for_user(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="seinfeld", name="Seinfeld")  # included in ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RO | AccessTokenAudience.CACHE_RW,
            is_org_admin=False,
        )
        repo = Repo.create(slug="bermuda", customer=customer, name="British")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post(
            "/api/v1/token/exchange/", data={"code": code, "desc": "He stopped short?", "remote_execution": "1"}
        )
        assert response.status_code == 200
        response_json = response.json()
        now = utcnow()
        access_token = response_json.pop("access_token")
        expiration = parse(response_json.pop("expires_at"))
        assert int(expiration.timestamp()) == pytest.approx(int((now + datetime.timedelta(days=180)).timestamp()))
        assert response_json == {"user": "cosmo", "repo": "bermuda"}
        claims = json.loads(jws.get_unverified_claims(access_token))
        assert jws.get_unverified_headers(access_token) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_refresh_token_key_id,
        }
        issued_at = claims.pop("iat")
        assert int((expiration - datetime.timedelta(days=180)).timestamp()) == pytest.approx(issued_at, rel=2)
        assert issued_at == pytest.approx(int(utcnow().timestamp()))
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert token.description == "He stopped short?"
        assert claims == {
            "jid": token.id,
            "exp": int(expiration.timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw"],
            "username": "cosmo",
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "toolchain_repo": repo.pk,
            "toolchain_customer": customer.pk,
        }
        assert AccessTokenExchangeCode.objects.count() == 1
        token_exchange = AccessTokenExchangeCode.objects.first()
        assert token_exchange.is_available is False

    def test_exchange_with_remote_execution_and_cache(self, client, user: ToolchainUser) -> None:
        customer = Customer.create(slug="seinfeld", name="Seinfeld")  # included in ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS
        customer.add_user(user)
        UserCustomerAccessConfig.create(
            customer_id=customer.id,
            user_api_id=user.api_id,
            audience=AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.REMOTE_EXECUTION,
            is_org_admin=False,
        )
        repo = Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        response = client.post(
            "/api/v1/token/exchange/", data={"code": code, "desc": "He stopped short?", "remote_execution": "1"}
        )
        assert response.status_code == 200
        response_json = response.json()
        now = utcnow()
        access_token = response_json.pop("access_token")
        expiration = parse(response_json.pop("expires_at"))
        assert int(expiration.timestamp()) == pytest.approx(int((now + datetime.timedelta(days=180)).timestamp()))
        assert response_json == {"user": "cosmo", "repo": "gold"}
        claims = json.loads(jws.get_unverified_claims(access_token))
        assert jws.get_unverified_headers(access_token) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_refresh_token_key_id,
        }
        issued_at = claims.pop("iat")
        assert int((expiration - datetime.timedelta(days=180)).timestamp()) == pytest.approx(issued_at, rel=2)
        assert issued_at == pytest.approx(int(utcnow().timestamp()))
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert token.description == "He stopped short?"
        assert claims == {
            "jid": token.id,
            "exp": int(expiration.timestamp()),
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw", "exec"],
            "username": "cosmo",
            "type": "refresh",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "toolchain_repo": repo.pk,
            "toolchain_customer": customer.pk,
        }
        assert AccessTokenExchangeCode.objects.count() == 1
        token_exchange = AccessTokenExchangeCode.objects.first()
        assert token_exchange.is_available is False
        assert token_exchange.state == AccessTokenExchangeCode.State.USED


@pytest.mark.django_db()
class TestAccessTokenRefreshView:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")

    @property
    def current_access_token_key_id(self) -> str:
        return settings.JWT_AUTH_KEY_DATA.get_current_access_token_key().key_id

    @pytest.fixture()
    def customer(self, user: ToolchainUser) -> Repo:
        customer = Customer.create(slug="yada", name="Yada Yada")
        customer.add_user(user)
        return customer

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")

    def test_get_api_access_token(self, user: ToolchainUser, repo: Repo) -> None:
        client = _get_client_with_refresh_token_auth_header(user=user, repo=repo)
        response = client.post("/api/v1/token/refresh/")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        json_response = response.json()
        expires_at = parse(json_response["token"]["expires_at"])
        token_str = _assert_access_token_response(json_response, repo, with_remote_cache=False)
        assert int(expires_at.timestamp()) == pytest.approx(
            int((utcnow() + datetime.timedelta(minutes=10)).timestamp())
        )
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_access_token_key_id,
        }
        now = utcnow()
        assert claims.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims == {
            "iss": "toolchain",
            "aud": ["dependency"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_customer": repo.customer_id,
            "toolchain_repo": repo.id,
            "toolchain_user": user.api_id,
            "username": "elaine",
        }

    def test_get_ui_access_token(self, user: ToolchainUser) -> None:
        client = _get_client_with_refresh_token_auth_header(user)
        response = client.post("/api/v1/token/refresh/")
        assert response.status_code == 200
        assert len(response.cookies) == 1
        cookie = assert_refresh_token_cookie(response)
        user_claims = check_refresh_token(cookie.value)
        assert isinstance(user_claims, UserClaims)
        assert user_claims.user_api_id == user.api_id
        json_response = response.json()
        assert set(json_response.keys()) == {"token"}
        token_data = json_response.pop("token")
        assert set(token_data.keys()) == {"access_token", "expires_at"}
        token_str = token_data["access_token"]
        expires_at = parse(token_data["expires_at"])
        assert int(expires_at.timestamp()) == pytest.approx(
            int((utcnow() + datetime.timedelta(minutes=10)).timestamp())
        )
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_access_token_key_id,
        }
        now = utcnow()
        assert claims.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=10)).timestamp()))
        assert claims == {
            "iss": "toolchain",
            "aud": ["frontend"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "username": "elaine",
        }

    def test_get_api_access_token_inactive_repo(self, user: ToolchainUser, repo: Repo) -> None:
        client = _get_client_with_refresh_token_auth_header(user=user, repo=repo)
        repo.deactivate()
        response = client.post("/api/v1/token/refresh/")
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid Refresh Token"}

    def test_get_api_access_token_inactive_customer(self, user: ToolchainUser, repo: Repo, customer: Customer) -> None:
        client = _get_client_with_refresh_token_auth_header(user=user, repo=repo)
        customer.deactivate()
        response = client.post("/api/v1/token/refresh/")
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid Refresh Token"}

    def test_get_api_access_token_limited_customer(self, user: ToolchainUser, repo: Repo, customer: Customer) -> None:
        client = _get_client_with_refresh_token_auth_header(user=user, repo=repo)
        customer.set_service_level(Customer.ServiceLevel.LIMITED)
        response = client.post("/api/v1/token/refresh/")
        assert response.status_code == 403
        assert response.json() == {
            "detail": "Invalid token request: Customer org has limited functionality.\nPlease contact Toolchain at support@toolchain.com",
            "rejected": True,
        }


@pytest.mark.django_db()
class TestRestrictedAccessTokenView:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(username="leo", email="leo@nyc.com", full_name="Uncle Leo", github_user_id="54665")

    @property
    def current_access_token_key_id(self) -> str:
        return settings.JWT_AUTH_KEY_DATA.get_current_access_token_key().key_id

    @pytest.fixture()
    def repo(self, user: ToolchainUser) -> Repo:
        customer = Customer.create(slug="yada", name="Yada Yada")
        customer.add_user(user)
        return Repo.create(slug="gold", customer=customer, name="Jerry Seinfeld is a funny guy")

    def _post(self, client, params: dict):
        return client.post("/api/v1/token/restricted/", data=json.dumps(params), content_type="application/json")

    def _assert_resolve_request(self, httpx_mock) -> dict:
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        # assert request.url == "http://scm-integration-api.tinsel.svc.cluster.local:80/api/v1/github/mi4K"
        return json.loads(request.read())

    def _assert_restricted_token(self, repo: Repo, user: ToolchainUser, response, ttl_minutes: int) -> None:
        assert response.status_code == 200
        assert RestrictedAccessToken.objects.count() == 1
        json_response = response.json()
        assert set(json_response.keys()) == {"token", "remote_cache"}
        token_data = json_response.pop("token")
        assert token_data.keys() == {"access_token", "expires_at", "customer_id", "repo_id"}
        assert token_data["customer_id"] == repo.customer_id
        assert token_data["repo_id"] == repo.id
        assert json_response["remote_cache"] == {"address": "grpcs://jerry.happy.festivus:443"}
        token_str = token_data["access_token"]
        expires_at = parse(token_data["expires_at"])
        assert int(expires_at.timestamp()) == pytest.approx(
            int((utcnow() + datetime.timedelta(minutes=10)).timestamp())
        )
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": self.current_access_token_key_id,
        }
        now = utcnow()
        token = RestrictedAccessToken.objects.first()
        assert token.repo_id == repo.pk
        assert token.ci_build_key == "trc_18_201412766_439751780"
        assert token.issued_at.timestamp() == pytest.approx(int(now.timestamp()))

        assert claims.pop("iat") == pytest.approx(int(now.timestamp()))
        assert claims.pop("exp") == pytest.approx(int((now + datetime.timedelta(minutes=ttl_minutes)).timestamp()))
        assert claims == {
            "jid": token.id,
            "iss": "toolchain",
            "aud": ["buildsense", "cache_rw", "impersonate"],
            "type": "access",
            "sub": "restricted",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "username": "leo",
            "toolchain_customer": repo.customer_id,
            "toolchain_repo": repo.pk,
        }

    def test_get_restricted_access_token_empty(self, client, user: ToolchainUser, repo: Repo) -> None:
        response = client.post("/api/v1/token/restricted/")
        assert RestrictedAccessToken.objects.count() == 0
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "repo_slug": [{"message": "This field is required.", "code": "required"}],
                "env": [{"message": "This field is required.", "code": "required"}],
            }
        }

    def test_get_restricted_access_token_no_ci_info(self, client, user: ToolchainUser, repo: Repo) -> None:
        response = self._post(client, {"repo_slug": "yada/gold"})
        assert RestrictedAccessToken.objects.count() == 0
        assert response.status_code == 400
        assert response.json() == {"errors": {"env": [{"message": "This field is required.", "code": "required"}]}}
        assert RestrictedAccessToken.objects.count() == 0

    def test_get_restricted_access_token_invalid_repo_slug(self, client, user: ToolchainUser, repo: Repo) -> None:
        params = {
            "repo_slug": "hello jerry",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert response.status_code == 400
        assert response.json() == {"errors": {"repo_slug": [{"message": "Invalid repo slug", "code": ""}]}}

    def test_get_restricted_access_token_repo_doesnt_exist(self, client, user: ToolchainUser, repo: Repo) -> None:
        params = {
            "repo_slug": "hello/jerry",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"repo_slug": [{"message": "repo not available at hello/jerry", "code": "not_found"}]}
        }

    def test_get_restricted_access_token_repo_customer_inactive(self, client, user: ToolchainUser, repo: Repo) -> None:
        repo.customer.deactivate()
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"repo_slug": [{"message": "repo not available at yada/gold", "code": "not_found"}]}
        }

    def test_get_restricted_access_token_no_env(self, client, user: ToolchainUser, repo: Repo) -> None:
        response = self._post(client, {"repo_slug": "hello/jerry"})
        assert response.status_code == 400
        assert response.json() == {"errors": {"env": [{"message": "This field is required.", "code": "required"}]}}

    def test_get_restricted_access_token_small_env(self, client, user: ToolchainUser, repo: Repo) -> None:
        params = {
            "repo_slug": "hello/jerry",
            "env": {"TRAVIS": "true"},
        }
        response = self._post(client, params)
        assert response.status_code == 400
        assert response.json() == {"errors": {"env": [{"message": "Missing env vars data", "code": ""}]}}

    def test_get_restricted_access_token_invalid_env(self, client, user: ToolchainUser, repo: Repo) -> None:
        params = {"repo_slug": "hello/jerry", "env": ["TRAVIS", "TRAVIS_PULL_REQUEST", "TRAVIS_BUILD_NUM"]}
        response = self._post(client, params)
        assert response.status_code == 400
        assert response.json() == {"errors": {"env": [{"message": "Invalid env vars data", "code": ""}]}}

    def test_get_restricted_access_token_reject(self, httpx_mock, client, user: ToolchainUser, repo: Repo) -> None:
        add_ci_resolve_error_response_for_repo(httpx_mock, repo, status=401, error="no token for you")
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert RestrictedAccessToken.objects.count() == 0
        assert response.status_code == 403
        assert response.json() == {"rejected": True}

    def test_get_restricted_access_token_with_ci_info(
        self, httpx_mock, client, user: ToolchainUser, repo: Repo
    ) -> None:
        assert RestrictedAccessToken.objects.count() == 0
        add_ci_resolve_response_for_repo(httpx_mock, repo, user_id="54665")
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        self._assert_restricted_token(repo, user, response, ttl_minutes=10)
        assert self._assert_resolve_request(httpx_mock) == {
            "ci_env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
            "started_treshold_sec": 360,
        }

    def test_get_restricted_access_token_max_tokens_exceeded(
        self, httpx_mock, client, user: ToolchainUser, repo: Repo
    ) -> None:
        for _ in range(3):
            RestrictedAccessToken.allocate(key="trc_18_201412766_439751780", repo_id=repo.id)
        assert RestrictedAccessToken.objects.count() == 3
        add_ci_resolve_response_for_repo(httpx_mock, repo, user_id="54665")
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert response.status_code == 403
        assert response.json() == {"rejected": True}
        assert self._assert_resolve_request(httpx_mock) == {
            "ci_env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
            "started_treshold_sec": 360,
        }

    def test_get_restricted_access_token_with_github_config(
        self, httpx_mock, client, user: ToolchainUser, repo: Repo
    ) -> None:
        assert RestrictedAccessToken.objects.count() == 0
        GithubRepoConfig.objects.create(
            repo_id=repo.id, max_build_tokens=6, started_treshold_sec=3600, token_ttl_sec=7 * 60
        )
        add_ci_resolve_response_for_repo(httpx_mock, repo, user_id="54665")
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert response.status_code == 200
        assert RestrictedAccessToken.objects.count() == 1
        self._assert_restricted_token(repo, user, response, ttl_minutes=7)
        assert self._assert_resolve_request(httpx_mock) == {
            "ci_env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
            "started_treshold_sec": 3600,
        }

    def test_get_restricted_access_token_unknown_user(
        self, httpx_mock, client, user: ToolchainUser, repo: Repo
    ) -> None:
        assert RestrictedAccessToken.objects.count() == 0
        GithubRepoConfig.objects.create(
            repo_id=repo.id, max_build_tokens=6, started_treshold_sec=3600, token_ttl_sec=7 * 60
        )
        add_ci_resolve_response_for_repo(httpx_mock, repo, user_id="77711")
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        response = self._post(client, params)
        assert response.status_code == 403
        assert response.json() == {"rejected": True}
        assert RestrictedAccessToken.objects.count() == 0
        assert self._assert_resolve_request(httpx_mock) == {
            "ci_env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
            "started_treshold_sec": 3600,
        }

    def test_get_restricted_access_token_unknown_inactive_user(
        self, httpx_mock, client, user: ToolchainUser, repo: Repo
    ) -> None:
        assert RestrictedAccessToken.objects.count() == 0
        GithubRepoConfig.objects.create(
            repo_id=repo.id, max_build_tokens=6, started_treshold_sec=3600, token_ttl_sec=7 * 60
        )
        add_ci_resolve_response_for_repo(httpx_mock, repo, user_id="54665")
        params = {
            "repo_slug": "yada/gold",
            "env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
        }
        user.deactivate()
        response = self._post(client, params)
        assert response.status_code == 403
        assert response.json() == {"rejected": True}
        assert RestrictedAccessToken.objects.count() == 0
        assert self._assert_resolve_request(httpx_mock) == {
            "ci_env": {"TRAVIS": "true", "TRAVIS_PULL_REQUEST": "2332", "TRAVIS_BUILD_NUM": "2221"},
            "started_treshold_sec": 3600,
        }


@pytest.mark.django_db()
class TestAccessTokenRefreshViewIntegration:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")

    def test_get_api_access_token(self, client, user: ToolchainUser) -> None:
        now = utcnow().replace(microsecond=0)
        customer = Customer.create(slug="yada", name="Yada Yada")
        customer.add_user(user)
        repo = Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.id,
            customer=customer,
            expiration_time=now + datetime.timedelta(days=30),
            audience=AccessTokenAudience.for_pants_client(),
            description="Three squares? You can’t spare three squares?",
        )
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        json_response = response.json()
        expires_at = parse(json_response["token"]["expires_at"])
        assert json_response["token"]["customer_id"] == customer.id
        token_str = _assert_access_token_response(json_response, repo)
        assert int(expires_at.timestamp()) == pytest.approx(
            int((utcnow() + datetime.timedelta(minutes=10)).timestamp()), rel=3
        )
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": _get_access_token_key_id(),
        }
        assert claims.pop("iat") == pytest.approx(now.timestamp())
        assert claims.pop("exp") == int(expires_at.timestamp())
        assert claims == {
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.pk,
            "toolchain_repo": repo.id,
            "toolchain_user": user.api_id,
            "username": "elaine",
        }

    def test_get_api_access_token_with_caching(self, client, user: ToolchainUser) -> None:
        now = utcnow().replace(microsecond=0)
        customer = Customer.create(slug="yada", name="Yada Yada")
        customer.add_user(user)
        repo = Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        audience = AccessTokenAudience.for_pants_client() | AccessTokenAudience.CACHE_RW
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.id,
            customer=customer,
            expiration_time=now + datetime.timedelta(days=30),
            audience=audience,
            description="Three squares? You can’t spare three squares?",
        )
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        json_response = response.json()
        expires_at = parse(json_response["token"]["expires_at"])
        token_str = _assert_access_token_response(json_response, repo)
        assert int(expires_at.timestamp()) == pytest.approx(
            int((utcnow() + datetime.timedelta(minutes=45)).timestamp())
        )
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": _get_access_token_key_id(),
        }
        assert claims.pop("iat") == pytest.approx(now.timestamp())
        assert claims.pop("exp") == int(expires_at.timestamp())
        assert claims == {
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.pk,
            "toolchain_repo": repo.id,
            "toolchain_user": user.api_id,
            "username": "elaine",
        }

    def _prepare_refresh_token(self, user: ToolchainUser) -> tuple[str, Customer]:
        now = utcnow().replace(microsecond=0)
        customer = Customer.create(slug="yada", name="Yada Yada")
        customer.add_user(user)
        repo = Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.id,
            customer=customer,
            expiration_time=now + datetime.timedelta(days=30),
            audience=AccessTokenAudience.for_pants_client(),
            description="Three squares? You can’t spare three squares?",
        )
        return token_str, customer

    def test_get_api_access_token_inactive_user(self, client, user: ToolchainUser) -> None:
        token_str, _ = self._prepare_refresh_token(user)
        user.deactivate()
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 403
        assert len(response.cookies) == 0
        assert response.json() == {"detail": "User N/A"}

    def test_get_api_access_token_inactive_customer(self, client, user: ToolchainUser) -> None:
        token_str, customer = self._prepare_refresh_token(user)
        customer.deactivate()
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid Refresh Token"}

    def test_get_api_access_token_user_no_longer_associated_with_customer(self, client, user: ToolchainUser) -> None:
        token_str, customer = self._prepare_refresh_token(user)
        customer.users.remove(user)
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 403
        assert len(response.cookies) == 0
        assert response.json() == {"detail": "Invalid Refresh Token"}

    def test_get_ui_access_token_with_token_header(self, client, user: ToolchainUser) -> None:
        now = utcnow().replace(microsecond=0)
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 200
        assert len(response.cookies) == 1
        cookie = assert_refresh_token_cookie(response)
        user_claims = check_refresh_token(cookie.value)
        assert isinstance(user_claims, UserClaims)
        assert user_claims.user_api_id == user.api_id
        json_response = response.json()
        assert json_response.keys()
        token_str = json_response["token"]["access_token"]
        expires_at = parse(json_response["token"]["expires_at"])
        assert int(expires_at.timestamp()) == pytest.approx(
            int((utcnow() + datetime.timedelta(minutes=10)).timestamp())
        )
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": _get_access_token_key_id(),
        }
        assert claims.pop("iat") == pytest.approx(now.timestamp())
        assert claims.pop("exp") == int(expires_at.timestamp())
        assert claims == {
            "iss": "toolchain",
            "aud": ["frontend"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_user": user.api_id,
            "username": "elaine",
        }

    def test_get_ui_access_token_revoked_token(self, client, user: ToolchainUser) -> None:
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        assert AllocatedRefreshToken.objects.count() == 1
        AllocatedRefreshToken.objects.first().revoke()
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert len(response.cookies) == 0
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid Refresh Token"}

    def test_get_ui_access_token_inactive_user(self, client, user: ToolchainUser) -> None:
        token_str, _ = get_or_create_refresh_token_for_ui(user)
        user.deactivate()
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 403
        assert len(response.cookies) == 0
        assert response.json() == {"detail": "Invalid Refresh Token"}

    def test_get_api_access_token_with_remote_exec(self, client, user: ToolchainUser) -> None:
        now = utcnow().replace(microsecond=0)
        customer = Customer.create(slug="yada", name="Yada Yada")
        customer.add_user(user)
        repo = Repo.create(slug="pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        audience = (
            AccessTokenAudience.for_pants_client() | AccessTokenAudience.CACHE_RW | AccessTokenAudience.REMOTE_EXECUTION
        )
        token_str = generate_refresh_token(
            user=user,
            repo_pk=repo.id,
            customer=customer,
            expiration_time=now + datetime.timedelta(days=30),
            audience=audience,
            description="Three squares? You can’t spare three squares?",
        )
        response = client.post("/api/v1/token/refresh/", HTTP_AUTHORIZATION=f"Bearer {token_str}")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        json_response = response.json()
        expires_at = parse(json_response["token"]["expires_at"])
        token_str = _assert_access_token_response(json_response, repo, with_remote_exec=True)
        assert int(expires_at.timestamp()) == pytest.approx(int((utcnow() + datetime.timedelta(hours=4)).timestamp()))
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "typ": "JWT",
            "alg": "HS256",
            "kid": _get_access_token_key_id(),
        }
        assert claims.pop("iat") == pytest.approx(now.timestamp())
        assert claims.pop("exp") == int(expires_at.timestamp())
        assert claims == {
            "iss": "toolchain",
            "aud": ["buildsense", "cache_ro", "cache_rw", "exec"],
            "type": "access",
            "toolchain_claims_ver": 2,
            "toolchain_customer": customer.pk,
            "toolchain_repo": repo.id,
            "toolchain_user": user.api_id,
            "username": "elaine",
        }


def _assert_access_token_response(
    json_response: dict, repo: Repo, with_remote_cache: bool = True, with_remote_exec: bool = False
) -> str:
    expected_keys = {"token"}
    if with_remote_cache:
        expected_keys.add("remote_cache")
    if with_remote_exec:
        expected_keys.add("remote_exec")
    assert set(json_response.keys()) == expected_keys
    if with_remote_cache:
        assert json_response["remote_cache"] == {"address": "grpcs://jerry.happy.festivus:443"}
    if with_remote_exec:
        assert json_response["remote_exec"] == {"address": "grpcs://jerry.happy.festivus:443"}
    token_data = json_response.pop("token")
    assert set(token_data.keys()) == {
        "access_token",
        "expires_at",
        "customer_id",
        "repo_id",
    }
    assert token_data["customer_id"] == repo.customer_id
    assert token_data["repo_id"] == repo.id
    return token_data["access_token"]
