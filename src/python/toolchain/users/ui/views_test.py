# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from http.cookies import Morsel
from urllib.parse import parse_qsl, urlparse

import pytest
from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth.views import PasswordChangeView
from django.http import HttpResponse
from django.test import Client
from django.urls import path
from jose import jws

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.claims import UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.models import AllocatedRefreshToken, Customer, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_bitbucket_user, create_github_user, create_staff
from toolchain.users.models import AuthProvider, ImpersonationSession, UserAuth, UserTermsOfServiceAcceptance
from toolchain.users.ui.auth_util_test import add_org_admins, load_fixture
from toolchain.users.ui.urls import urlpatterns as user_url_pattens
from toolchain.util.test.util import convert_headers_to_wsgi

urlpatterns = [path("auth/password_change/", PasswordChangeView.as_view())] + user_url_pattens


def accept_tos(user: ToolchainUser) -> None:
    UserTermsOfServiceAcceptance.accept_tos(
        user_api_id=user.api_id,
        tos_version="hello-newman-2022",
        client_ip="188.222.88.111",
        user_email="jerry@sein.com",
        request_id="festivus-miracle",
    )


def assert_get_org_admin_request(req, slug: str) -> None:
    assert req.method == "GET"
    assert req.url == f"https://api.github.com/orgs/{slug}/members?role=admin&per_page=100"
    assert req.headers["Authorization"] == "token art-corvelay"


def _get_client(user: ToolchainUser) -> Client:
    claims = UserClaims(
        user_api_id=user.api_id,
        username=user.username,
        audience=AccessTokenAudience.FRONTEND_API,
        token_type=AccessTokenType.ACCESS_TOKEN,
        token_id=None,
    )
    headers = create_internal_auth_headers(user, claims=claims.as_json_dict(), impersonation=None)
    client = Client(**convert_headers_to_wsgi(headers))
    client.force_login(user)
    return client


def assert_refresh_token_cookie(response) -> Morsel:
    assert "refreshToken" in response.cookies
    cookie = response.cookies["refreshToken"]
    assert cookie["max-age"] == 864_000
    assert cookie["httponly"] == ""
    assert cookie["samesite"] == "Lax"
    return cookie


def assert_known_user_cookie(response) -> None:
    assert "tcuser" in response.cookies
    cookie = response.cookies["tcuser"]
    assert cookie["max-age"] == ""
    assert cookie["httponly"] == ""
    assert cookie["samesite"] == "Lax"


@pytest.mark.django_db()
@pytest.mark.urls(__name__)
class TestLoginView:
    _INFOSITE_URLS = [
        "https://toolchain.com",
        "HTTPS://TOOLCHAIN.COM",
        "HTTps://ToolChain.Com",
    ]

    def _assert_onboarding(self, context_data: dict):
        assert context_data["pants_version"] == "2.12"
        assert context_data["docs_link"] == "https://docs.toolchain.com/docs"
        assert context_data["onboarding_link"] == "https://www.pantsbuild.org/docs/getting-started"

    def test_login_view_default(self, client) -> None:
        response = client.get("/auth/login/")
        assert response.status_code == 200
        assert response.template_name == ["users/login.html"]
        assert response.context_data["show_onboarding"] is False
        self._assert_onboarding(response.context_data)
        assert response.context_data["login_options"] == [
            ("github", "Github", "black-button", "/auth/login/github/"),
            # ("bitbucket", "Bitbucket", "blue-button", "/auth/login/bitbucket/"),
        ]

    def test_login_view_with_next_param_default(self, client) -> None:
        response = client.get("/auth/login/?next=http://testtest.jerry/some/place/else")
        assert response.status_code == 200
        assert response.template_name == ["users/login.html"]
        self._assert_onboarding(response.context_data)
        assert response.context_data["show_onboarding"] is False
        assert response.context_data["login_options"] == [
            (
                "github",
                "Github",
                "black-button",
                "/auth/login/github/?next=http%3A%2F%2Ftesttest.jerry%2Fsome%2Fplace%2Felse",
            ),
            # (
            #     "bitbucket",
            #     "Bitbucket",
            #     "blue-button",
            #     "/auth/login/bitbucket/?next=http%3A%2F%2Ftesttest.jerry%2Fsome%2Fplace%2Felse",
            # ),
        ]

    @pytest.mark.parametrize("referrer", _INFOSITE_URLS)
    def test_login_view_from_infosite(self, client, referrer: str) -> None:
        response = client.get("/auth/login/", HTTP_REFERER=referrer)
        assert response.status_code == 200
        assert response.template_name == ["users/login.html"]
        assert response.context_data["show_onboarding"] is True
        self._assert_onboarding(response.context_data)

    @pytest.mark.parametrize("referrer", _INFOSITE_URLS)
    def test_login_view_from_infosite_existing_tc_user(self, client, referrer: str) -> None:
        client.cookies["tcuser"] = "1"
        response = client.get("/auth/login/", HTTP_REFERER=referrer)
        assert response.status_code == 200
        assert response.template_name == ["users/login.html"]
        assert response.context_data["show_onboarding"] is False
        self._assert_onboarding(response.context_data)

    def test_login_view_from_infosite_force_show(self, client) -> None:
        client.cookies["tcuser"] = "1"
        response = client.get("/auth/login/?onboarding=1")
        assert response.status_code == 200
        assert response.template_name == ["users/login.html"]
        assert response.context_data["show_onboarding"] is True
        self._assert_onboarding(response.context_data)


@pytest.mark.django_db()
@pytest.mark.urls(__name__)
class BaseAuthViewsTest:
    def assert_last_login(self, user: ToolchainUser) -> None:
        now = utcnow().timestamp()
        assert user.last_login is not None
        assert user.last_login.timestamp() == pytest.approx(now)

    def _assert_access_denied(self, client, response) -> None:
        assert AllocatedRefreshToken.objects.count() == 0
        assert response.status_code == 302
        assert response.url.startswith("/auth/denied/")
        assert "_auth_user_id" not in client.session

    def _assert_successful_login_cookies(self, response: HttpResponse, expected_user: ToolchainUser) -> str:
        assert AllocatedRefreshToken.objects.count() == 1
        stored_token = AllocatedRefreshToken.objects.first()
        assert stored_token.usage == AllocatedRefreshToken.Usage.UI
        assert len(response.cookies) == 3
        # assert deletion of the seesionid cookie since after login we don't want to use django sessions anymore
        assert "sessionid" in response.cookies
        assert response.cookies["sessionid"].value == ""
        assert_known_user_cookie(response)
        cookie = assert_refresh_token_cookie(response)
        cookie_expiration = parse(cookie["expires"])
        token_str = cookie.value
        claims = json.loads(jws.get_unverified_claims(token_str))
        assert jws.get_unverified_headers(token_str) == {
            "alg": "HS256",
            "typ": "JWT",
            "kid": settings.JWT_AUTH_KEY_DATA.get_current_refresh_token_key().key_id,
        }
        assert claims["jid"] == stored_token.id
        assert claims["aud"] == ["frontend"]
        assert claims["username"] == expected_user.username
        assert claims["type"] == "refresh"
        assert claims["toolchain_user"] == expected_user.api_id
        cookie_expiration_ts = int(cookie_expiration.timestamp())
        # Django will add a second to the cookie expiration to compensate compute time.
        # see: https://github.com/django/django/blob/ebd78a9f97d8ba850d279a844d89a1d805370738/django/http/response.py#L178
        assert claims["exp"] == cookie_expiration_ts or claims["exp"] == cookie_expiration_ts - 1
        return claims["toolchain_user"]

    def assert_no_session(self, client, response):
        assert len(client.session.keys()) == 0
        assert "refreshToken" in response.cookies
        cookie = response.cookies["sessionid"]
        assert cookie.value == ""


class TestGithubAuthViews(BaseAuthViewsTest):
    @pytest.fixture(autouse=True)
    def _update_settings(self, settings):
        settings.SOCIAL_AUTH_GITHUB_KEY = "good-for-the-tuna"
        settings.SOCIAL_AUTH_GITHUB_SECRET = "tuna-salad"

    def _prepare_session(self, client, state: str, next_url: str | None = None) -> None:
        client.logout()
        session = client.session  # Must grab it into a variable.
        session["github_state"] = state
        if next_url:
            session["next"] = next_url
        session.save()

    def _assert_user_auth(
        self,
        user: ToolchainUser,
        user_id: str,
        emails: tuple[str, ...] = ("12688+jerry@users.noreply.github.com", "jerry@nbc.com"),
    ) -> None:
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.provider == AuthProvider.GITHUB
        assert user_auth.user_id == user_id
        assert user_auth.user_api_id == user.api_id
        assert user_auth.email_addresses == emails

    def test_start_github_auth(self, client) -> None:
        client.logout()
        response = client.get("/auth/login/github/")
        assert response.status_code == 302
        assert "github_state" in client.session
        saved_state = client.session["github_state"]
        assert response.url.startswith("https://github.com/login/oauth/authorize?client_id")
        query_params = dict(parse_qsl(urlparse(response.url).query))
        assert "state" in query_params
        state = query_params["state"]
        assert isinstance(state, str)
        assert len(state) > 12
        assert query_params == {
            "client_id": "good-for-the-tuna",
            "redirect_uri": "http://testserver/auth/complete/github/",
            "response_type": "code",
            "state": saved_state,
        }

    def test_redirect_to_login_view(self, client) -> None:
        # This is somewhat contrived since we don't exposes those paths to users (via service router)
        client.logout()
        response = client.get("/auth/password_change/")
        assert response.status_code == 302
        assert response.url == "/accounts/login/?next=/auth/password_change/"

    def _add_github_files_fixtures(self, responses) -> None:
        responses.add(
            responses.POST, "https://github.com/login/oauth/access_token", json={"access_token": "art-corvelay"}
        )
        responses.add(responses.GET, "https://api.github.com/user/emails", json=load_fixture("github_user_emails"))
        responses.add(responses.GET, "https://api.github.com/user", json=load_fixture("github_user"))
        responses.add(responses.GET, "https://api.github.com/user/orgs", json=[])
        responses.add(responses.GET, "https://api.github.com/users/jerry/orgs", json=load_fixture("github_user_orgs"))

    def _add_github_fixtures(
        self,
        responses,
        username: str,
        uid: str,
        emails: tuple[str, ...],
        org: str | None,
        avatar_url: str | None = None,
        html_url: str | None = None,
        full_name: str | None = None,
        created_at: datetime.datetime | None = None,
    ) -> None:
        assert isinstance(emails, tuple)
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={
                "email": emails[0],
                "login": username,
                "id": uid,
                "name": full_name or "Cosmo Kramer",
                "avatar_url": avatar_url or "https://handh.com/bagels.jpg",
                "html_url": html_url or "https://soup-man.org/jambalaya",
                "created_at": (created_at or datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc)).isoformat(),
            },
        )
        responses.add(
            responses.POST, "https://github.com/login/oauth/access_token", json={"access_token": "art-corvelay"}
        )
        email_response = [{"email": email, "verified": True, "primary": False} for email in emails]
        email_response[0]["primary"] = True
        responses.add(
            responses.GET,
            "https://api.github.com/user/emails",
            json=email_response,
        )
        responses.add(
            responses.GET, "https://api.github.com/user/orgs", json=[{"login": "apt-5e"}, {"login": org}] if org else []
        )
        responses.add(
            responses.GET, f"https://api.github.com/users/{username}/orgs", json=[{"login": org}] if org else []
        )

    def test_complete_github_auth_new_user(self, responses, client) -> None:
        self._add_github_files_fixtures(responses)
        add_org_admins(responses, org_slugs=("seinfeld",))
        customer = Customer.create("seinfeld", "Seinfeld Corp")  # allow the org
        self._prepare_session(client, "chicken-salad")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "chicken-salad", "code": "gh-code"})
        self.assert_no_session(client, response)
        assert response.status_code == 302
        assert response.url == "/tos/"
        assert ToolchainUser.objects.count() == 1
        user_api_id = self._assert_successful_login_cookies(response, ToolchainUser.objects.first())
        user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert user is not None
        assert user.username == "jerry"
        assert user.full_name == "Jerry Seinfeld"
        assert user.email == "jerry@nbc.com"
        assert user.avatar_url == "https://avatars1.githubusercontent.com/u/1288?v=4"
        assert user.customers.count() == 1
        assert user.customers.first().pk == customer.pk
        self.assert_last_login(user)
        self._assert_user_auth(user, "113311")
        assert_get_org_admin_request(responses.calls[-1].request, "seinfeld")

    def test_complete_github_auth_existing_user_no_tos(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp")  # Allow the org
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer")
        self._add_github_fixtures(
            responses,
            "kramer",
            "71123",
            emails=("jerry@nbc.com",),
            org="seinfeld",
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Cosmo KRAMER",
        )
        add_org_admins(responses, org_slugs=("seinfeld",))
        self._prepare_session(client, "little-jerry-seinfeld")

        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})

        user_api_id = self._assert_successful_login_cookies(response, user)
        self.assert_no_session(client, response)
        assert response.status_code == 302
        assert response.url == "/tos/"
        assert ToolchainUser.objects.count() == 1
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "cosmo"
        assert loaded_user.email == "cosmo@jerrysplace.com"
        assert loaded_user.full_name == "Cosmo KRAMER"
        assert loaded_user.avatar_url == "https://hnh.com/no-bagels.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "71123", emails=("jerry@nbc.com",))
        assert_get_org_admin_request(responses.calls[-1].request, "seinfeld")

    def test_complete_github_auth_existing_user_full_name_set_with_tos(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp")  # Allow the org
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer", full_name="C. Kramer")
        accept_tos(user)
        self._add_github_fixtures(
            responses,
            "kramer",
            "71123",
            emails=("jerry@nbc.com",),
            org="seinfeld",
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Cosmo KRAMER",
        )
        add_org_admins(responses, org_slugs=("seinfeld",))
        self._prepare_session(client, "little-jerry-seinfeld")

        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        user_api_id = self._assert_successful_login_cookies(response, user)
        self.assert_no_session(client, response)
        assert response.status_code == 302
        assert response.url == "/"
        assert ToolchainUser.objects.count() == 1
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "cosmo"
        assert loaded_user.email == "cosmo@jerrysplace.com"
        assert loaded_user.full_name == "C. Kramer"
        assert loaded_user.avatar_url == "https://hnh.com/no-bagels.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "71123", emails=("jerry@nbc.com",))
        assert_get_org_admin_request(responses.calls[-1].request, "seinfeld")

    def test_complete_github_auth_existing_inactive_user(self, responses, client):
        Customer.create("seinfeld", "Seinfeld Corp")  # whitelist the org
        user = create_github_user("cosmo", github_user_id="662772", github_username="kramer")
        user.deactivate()
        self._add_github_fixtures(responses, "kramer", "662772", emails=("kramer@nbc.com",), org="seinfeld")

        self._prepare_session(client, "little-jerry-seinfeld")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        self._assert_access_denied(client, response)
        assert ToolchainUser.objects.count() == 1
        assert AllocatedRefreshToken.objects.count() == 0
        user = ToolchainUser.objects.first()
        assert user.is_active is False
        assert user.customers.count() == 0
        assert UserAuth.objects.count() == 1

    def test_complete_github_auth_existing_inactive_user_no_org(self, responses, client):
        self._add_github_fixtures(responses, "kramer", "662772", emails=("kramer@nbc.com",), org=None)
        user = create_github_user("cosmo", github_user_id="662772", github_username="kramer")
        user.deactivate()
        self._prepare_session(client, "little-jerry-seinfeld")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        self._assert_access_denied(client, response)
        assert ToolchainUser.objects.count() == 1
        assert AllocatedRefreshToken.objects.count() == 0
        user = ToolchainUser.objects.first()
        assert user.is_active is False
        assert user.customers.count() == 0
        assert UserAuth.objects.count() == 1

    def test_complete_github_auth_app_install(self, client) -> None:
        response = client.get("/auth/complete/github/", data={"setup_action": "install"})
        assert response.status_code == 302
        assert response.url == "/"

    def test_complete_github_auth_existing_user_email_change_no_tos(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp")  # whitelist the org
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer", email="cosmo@kramer.com")
        self._add_github_fixtures(
            responses,
            "kramer",
            "71123",
            emails=("jerry@nbc.com",),
            org="seinfeld",
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Cosmo KRAMER",
        )
        add_org_admins(responses, org_slugs=("seinfeld",))
        self._prepare_session(client, "little-jerry-seinfeld")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        user_api_id = self._assert_successful_login_cookies(response, user)
        self.assert_no_session(client, response)
        assert response.status_code == 302
        assert response.url == "/tos/"
        assert ToolchainUser.objects.count() == 1
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "cosmo"
        assert loaded_user.email == "cosmo@kramer.com"
        assert loaded_user.full_name == "Cosmo KRAMER"
        assert loaded_user.avatar_url == "https://hnh.com/no-bagels.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        assert_get_org_admin_request(responses.calls[-1].request, "seinfeld")
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "71123", emails=("jerry@nbc.com",))

    def test_complete_github_auth_inactive_user_via_user_auth(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp")  # allow users associated with this org via GH
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer")
        UserAuth.update_or_create(
            user=user, user_id="71123", provider=AuthProvider.GITHUB, username="cosmo", emails=["kramer@nbc.com"]
        )
        user.deactivate()
        self._add_github_fixtures(
            responses,
            "kramer",
            "71123",
            emails=("jerry@nbc.com",),
            org=customer.slug,
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Cosmo KRAMER",
        )
        self._prepare_session(client, "little-jerry-seinfeld")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        self._assert_access_denied(client, response)
        assert AllocatedRefreshToken.objects.count() == 0

    def test_complete_auth_existing_username_different_case(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp", scm=Customer.Scm.GITHUB)
        create_bitbucket_user("CosmO", bitbucket_user_id="99999222", bitbucket_username="kramer")
        self._add_github_fixtures(
            responses,
            "cosmo",
            "822331",
            emails=("cosmo@nbc.com", "kramer@nyc.com"),
            org=customer.slug,
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Cosmo KRAMER",
        )
        add_org_admins(responses, org_slugs=("seinfeld",))
        self._prepare_session(client, "mandelbaum")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "mandelbaum", "code": "no1dad"})
        user_api_id = self._assert_successful_login_cookies(response, ToolchainUser.objects.get(email="cosmo@nbc.com"))
        self.assert_no_session(client, response)
        assert ToolchainUser.objects.count() == 2
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username.startswith("cosmo-github-")
        assert len(loaded_user.username) == 18
        assert loaded_user.full_name == "Cosmo KRAMER"
        assert loaded_user.email == "cosmo@nbc.com"
        assert loaded_user.avatar_url == "https://hnh.com/no-bagels.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        assert_get_org_admin_request(responses.calls[-1].request, "seinfeld")
        user_auth = UserAuth.objects.get(user_id="822331")
        assert user_auth.provider == AuthProvider.GITHUB
        assert user_auth.user_id == "822331"
        assert user_auth.user_api_id == loaded_user.api_id
        assert user_auth.email_addresses == ("cosmo@nbc.com", "kramer@nyc.com")

    @pytest.mark.xfail(reason="disabled self service onboarding", strict=True, raises=AssertionError)
    def test_complete_github_auth_self_service_onbaording(self, responses, client) -> None:
        self._add_github_fixtures(responses, "kramer", "87387", emails=("kramer@nbc.com",), org="seinfeld")
        self._prepare_session(client, "chicken-salad")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "chicken-salad", "code": "gh-code"})
        assert ToolchainUser.objects.count() == 1
        user_api_id = self._assert_successful_login_cookies(response, ToolchainUser.objects.first())
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "kramer"
        assert loaded_user.full_name == "Cosmo Kramer"
        assert loaded_user.email == "kramer@nbc.com"
        assert loaded_user.avatar_url == "https://handh.com/bagels.jpg"
        assert loaded_user.customers.count() == 0
        assert loaded_user.is_associated_with_active_customers() is False
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "87387", emails=("kramer@nbc.com",))

    def test_complete_github_auth_new_user_no_tos_with_redirect(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp")
        assert ToolchainUser.objects.count() == 0
        self._add_github_fixtures(
            responses,
            "kramer",
            "883747847",
            emails=("jerry@nbc.com",),
            org="seinfeld",
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Jerry Seinfeld",
            created_at=utcnow() - datetime.timedelta(hours=2),
        )
        add_org_admins(responses, org_slugs=("seinfeld",))
        self._prepare_session(client, "little-jerry-seinfeld", next_url="http://testserver/api/v1/token/auth/")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        assert ToolchainUser.objects.count() == 1
        user = ToolchainUser.objects.first()
        user_api_id = self._assert_successful_login_cookies(response, user)
        self.assert_no_session(client, response)
        assert response.status_code == 302
        assert response.url == "/tos/?next=http%3A//testserver/api/v1/token/auth/"
        assert ToolchainUser.objects.count() == 1
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "kramer"
        assert loaded_user.email == "jerry@nbc.com"
        assert loaded_user.full_name == "Jerry Seinfeld"
        assert loaded_user.avatar_url == "https://hnh.com/no-bagels.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        assert_get_org_admin_request(responses.calls[-1].request, "seinfeld")
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "883747847", emails=("jerry@nbc.com",))

    @pytest.mark.xfail(reason="disabled self service onboarding", strict=True, raises=AssertionError)
    def test_complete_github_auth_new_gitub_user_denied(self, responses, client) -> None:
        assert ToolchainUser.objects.count() == 0
        self._add_github_fixtures(
            responses,
            "kramer",
            "883747847",
            emails=("jerry@nbc.com",),
            org="seinfeld",
            avatar_url="https://hnh.com/no-bagels.jpg",
            html_url="https://soup-man.org/jambalaya",
            full_name="Jerry Seinfeld",
            created_at=utcnow() - datetime.timedelta(hours=7),
        )
        self._prepare_session(client, "little-jerry-seinfeld", next_url="http://testserver/api/v1/token/auth/")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        self._assert_access_denied(client, response)
        assert ToolchainUser.objects.count() == 1
        loaded_user = ToolchainUser.objects.first()
        assert loaded_user is not None
        assert loaded_user.username == "kramer"
        assert loaded_user.email == "jerry@nbc.com"
        assert loaded_user.full_name == "Jerry Seinfeld"
        assert loaded_user.avatar_url == ""  # since update_user_details won't be called.
        assert loaded_user.is_active is False
        assert loaded_user.customers.count() == 0

    def test_complete_github_auth_no_verified_emails_http_403_from_github(self, responses, client) -> None:
        assert ToolchainUser.objects.count() == 0
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={
                "email": "jerry@nbc.com",
                "login": "kramer",
                "id": "8888882222",
                "name": "Cosmo Kramer",
                "avatar_url": "https://handh.com/bagels.jpg",
                "html_url": "https://soup-man.org/jambalaya",
                "created_at": datetime.datetime(2020, 1, 22, tzinfo=datetime.timezone.utc).isoformat(),
            },
        )
        responses.add(
            responses.POST, "https://github.com/login/oauth/access_token", json={"access_token": "art-corvelay"}
        )
        responses.add(responses.GET, "https://api.github.com/user/emails", status=403, body="Broccoli...Vile Weed!")
        self._prepare_session(client, "little-jerry-seinfeld", next_url="http://testserver/api/v1/token/auth/")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/github/", data={"state": "little-jerry-seinfeld", "code": "gh-code"})
        self._assert_access_denied(client, response)
        assert ToolchainUser.objects.count() == 0


class TestBitBucketAuthViews(BaseAuthViewsTest):
    @pytest.fixture(autouse=True)
    def _update_settings(self, settings):
        settings.SOCIAL_AUTH_BITBUCKET_KEY = "tuna-on-toast"
        settings.SOCIAL_AUTH_BITBUCKET_SECRET = "chicken-salad-on-rye"

    def _prepare_session(self, client, state: str) -> None:
        client.logout()
        session = client.session  # Must grab it into a variable.
        session["bitbucket_state"] = state
        session.save()

    def _assert_user_auth(
        self,
        user: ToolchainUser,
        user_id: str,
        username: str,
        emails: tuple[str, ...] = ("jerry@seinfeld.com",),
    ) -> None:
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.provider == AuthProvider.BITBUCKET
        assert user_auth.user_id == user_id
        assert user_auth.user_api_id == user.api_id
        assert user_auth.email_addresses == emails
        assert user_auth.username == username

    def _add_bitbucket_files_fixtures(self, responses) -> None:
        responses.add(
            responses.POST,
            "https://bitbucket.org/site/oauth2/access_token",
            json={"access_token": "against-the-current"},
        )
        responses.add(
            responses.GET, "https://api.bitbucket.org/2.0/user/emails", json=load_fixture("bitbucket_user_emails")
        )
        responses.add(responses.GET, "https://api.bitbucket.org/2.0/user", json=load_fixture("bitbucket_user"))
        responses.add(
            responses.GET, "https://api.bitbucket.org/2.0/workspaces", json=load_fixture("bitbucket_workspaces")
        )

    def _add_bitbucket_fixtures(
        self,
        responses,
        username: str,
        uid: str,
        emails: tuple[str, ...],
        org: str,
        avatar_url: str | None = None,
        full_name: str | None = None,
    ) -> None:
        assert isinstance(emails, tuple)
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/user",
            json={
                "username": username,
                "account_id": uid,
                "display_name": full_name or "George Costanza",
                "links": {
                    "avatar": {"href": avatar_url or "https://salad.com/rye.jpg"},
                },
            },
        )
        responses.add(
            responses.POST,
            "https://bitbucket.org/site/oauth2/access_token",
            json={"access_token": "against-the-current"},
        )
        emails_values = [
            {"is_primary": False, "is_confirmed": True, "type": "email", "email": email} for email in emails
        ]
        emails_values[0]["is_primary"] = True
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/user/emails",
            json={
                "pagelen": 10,
                "values": emails_values,
                "page": 1,
                "size": len(emails),
            },
        )
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/workspaces",
            json={
                "pagelen": 10,
                "page": 1,
                "size": 1,
                "values": [
                    {
                        "created_on": "2018-11-14T19:15:05.058566+00:00",
                        "type": "workspace",
                        "slug": org,
                    }
                ],
            },
        )

    def test_start_auth(self, client) -> None:
        client.logout()
        response = client.get("/auth/login/bitbucket/")
        assert response.status_code == 302
        assert set(client.session.keys()) == {"bitbucket_state"}
        saved_state = client.session["bitbucket_state"]
        assert response.url.startswith("https://bitbucket.org/site/oauth2/authorize?")
        query_params = dict(parse_qsl(urlparse(response.url).query))
        assert "state" in query_params
        state = query_params["state"]
        assert isinstance(state, str)
        assert len(state) > 12
        assert query_params == {
            "client_id": "tuna-on-toast",
            "redirect_uri": "http://testserver/auth/complete/bitbucket/",
            "response_type": "code",
            "state": saved_state,
        }

    def test_complete_auth_new_user(self, responses, client) -> None:
        self._add_bitbucket_files_fixtures(responses)
        customer = Customer.create("newman", "Hello Newman", scm=Customer.Scm.BITBUCKET)  # whitelist the org
        self._prepare_session(client, "good-for-the-tuna")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/bitbucket/", data={"state": "good-for-the-tuna", "code": "salmon"})
        assert response.status_code == 302
        assert response.url == "/tos/"
        self.assert_no_session(client, response)
        assert ToolchainUser.objects.count() == 1
        user_api_id = self._assert_successful_login_cookies(response, ToolchainUser.objects.first())
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "jerry"
        assert loaded_user.full_name == "Jerry Seinfeld"
        assert loaded_user.email == "jerry@seinfeld.com"
        assert loaded_user.avatar_url == "https://secure.gravatar.com/jerrys.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "6059303e630024006f000000", username="jerry")

    def test_complete_auth_existing_user_with_tos(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp", scm=Customer.Scm.BITBUCKET)  # whitelist the org
        user = create_bitbucket_user(
            "cosmo",
            bitbucket_user_id="00999288347474",
            email="cosmo@nyc.com",
            full_name="Cosmo Kramer",
            bitbucket_username="k-man",
        )
        accept_tos(user)
        self._add_bitbucket_fixtures(
            responses,
            username="kramer",  # different than the toolchain username, which is fine.
            uid="00999288347474",
            emails=("kramer@nyc.com",),
            org="seinfeld",
            avatar_url="https://bagel.com/magic-crepe.jpg",
            full_name="Cosmo KRAMER",
        )
        self._prepare_session(client, "mandelbaum")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/bitbucket/", data={"state": "mandelbaum", "code": "no1dad"})
        assert response.status_code == 302
        assert response.url == "/"
        self.assert_no_session(client, response)
        assert ToolchainUser.objects.count() == 1
        user_api_id = self._assert_successful_login_cookies(response, user)
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username == "cosmo"
        assert loaded_user.email == "cosmo@nyc.com"
        assert loaded_user.full_name == "Cosmo Kramer"
        assert loaded_user.avatar_url == "https://bagel.com/magic-crepe.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        self._assert_user_auth(loaded_user, "00999288347474", username="kramer", emails=("kramer@nyc.com",))

    def test_complete_auth_existing_username(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp", scm=Customer.Scm.BITBUCKET)  # whitelist the org
        create_github_user("cosmo")
        self._add_bitbucket_fixtures(
            responses,
            username="cosmo",
            uid="00999288347474",
            emails=("kramer@nyc.com",),
            org="seinfeld",
            avatar_url="https://bagel.com/magic-crepe-22.jpg",
            full_name="Cosmo Kramer",
        )
        self._prepare_session(client, "mandelbaum")
        assert AllocatedRefreshToken.objects.count() == 0
        assert ToolchainUser.objects.count() == 1
        response = client.get("/auth/complete/bitbucket/", data={"state": "mandelbaum", "code": "no1dad"})
        self.assert_no_session(client, response)
        assert ToolchainUser.objects.count() == 2
        user_api_id = self._assert_successful_login_cookies(response, ToolchainUser.objects.get(email="kramer@nyc.com"))
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.username.startswith("cosmo-bitbucket-")
        assert len(loaded_user.username) == 21
        assert loaded_user.username == loaded_user.username.lower()
        assert loaded_user.full_name == "Cosmo Kramer"
        assert loaded_user.email == "kramer@nyc.com"
        assert loaded_user.avatar_url == "https://bagel.com/magic-crepe-22.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        user_auth = UserAuth.objects.get(user_id="00999288347474")
        assert user_auth.provider == AuthProvider.BITBUCKET
        assert user_auth.user_id == "00999288347474"
        assert user_auth.user_api_id == loaded_user.api_id
        assert user_auth.email_addresses == ("kramer@nyc.com",)

    def test_complete_auth_existing_email(self, responses, client) -> None:
        customer = Customer.create("seinfeld", "Seinfeld Corp", scm=Customer.Scm.BITBUCKET)  # whitelist the org
        existing_user = create_bitbucket_user(
            "kenny",
            bitbucket_user_id="888888888",
            email="cosmo@nyc.com",
            full_name="Kenny Kramer",
            bitbucket_username="k-man",
        )
        self._add_bitbucket_fixtures(
            responses,
            username="cosmo",
            uid="00999288347474",
            emails=("cosmo@nyc.com", "cosmo@seinfeld.com"),
            org="seinfeld",
            avatar_url="https://bagel.com/magic-crepe-22.jpg",
            full_name="Cosmo Kramer",
        )
        self._prepare_session(client, "mandelbaum")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/bitbucket/", data={"state": "mandelbaum", "code": "no1dad"})
        self.assert_no_session(client, response)
        assert ToolchainUser.objects.count() == 2
        user_api_id = self._assert_successful_login_cookies(
            response, ToolchainUser.objects.get(email="cosmo@seinfeld.com")
        )
        loaded_user = ToolchainUser.get_by_api_id(api_id=user_api_id)
        assert loaded_user is not None
        assert loaded_user.id != existing_user.id
        assert loaded_user.username == "cosmo"
        assert loaded_user.full_name == "Cosmo Kramer"
        assert loaded_user.email == "cosmo@seinfeld.com"
        assert loaded_user.avatar_url == "https://bagel.com/magic-crepe-22.jpg"
        assert loaded_user.customers.count() == 1
        assert loaded_user.customers.first().pk == customer.pk
        self.assert_last_login(loaded_user)
        assert UserAuth.objects.count() == 2
        user_auth = UserAuth.objects.get(user_id="00999288347474")
        assert user_auth.provider == AuthProvider.BITBUCKET
        assert user_auth.user_id == "00999288347474"
        assert user_auth.user_api_id == loaded_user.api_id
        assert user_auth.email_addresses == ("cosmo@nyc.com", "cosmo@seinfeld.com")
        assert user_auth.username == "cosmo"

    def test_complete_auth_existing_email_no_available_email(self, responses, client) -> None:
        Customer.create("seinfeld", "Seinfeld Corp", scm=Customer.Scm.BITBUCKET)  # whitelist the org
        create_bitbucket_user(
            "kenny",
            bitbucket_user_id="888888888",
            email="cosmo@nyc.com",
            full_name="Kenny Kramer",
            bitbucket_username="k-man",
        )
        self._add_bitbucket_fixtures(
            responses,
            username="cosmo",
            uid="00999288347474",
            emails=("cosmo@nyc.com",),
            org="seinfeld",
            avatar_url="https://bagel.com/magic-crepe-22.jpg",
            full_name="Cosmo Kramer",
        )
        self._prepare_session(client, "mandelbaum")
        assert AllocatedRefreshToken.objects.count() == 0
        response = client.get("/auth/complete/bitbucket/", data={"state": "mandelbaum", "code": "no1dad"})
        self._assert_access_denied(client, response)


@pytest.mark.urls(__name__)
def test_access_denied_view(client) -> None:
    response = client.get("/auth/denied/")
    assert response.status_code == 403
    assert response.template_name == ["users/error.html"]
    assert response.context_data["error_message"] == "You are not currently registered as a Toolchain user."
    response.render()
    assert "You are not currently registered as a Toolchain user." in response.content.decode()


@pytest.mark.django_db()
@pytest.mark.urls(__name__)
class TestLogoutView:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(username="kramer", email="kramer@jerrysplace.com")

    def test_logout_via_get(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.get("/auth/logout/")
        assert response.status_code == 302
        assert response.url == "/"
        cookies = response.cookies
        assert cookies["refreshToken"].value == ""
        assert cookies["sessionid"].value == ""

    def test_logout_via_post(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.post("/auth/logout/")
        assert response.status_code == 302
        assert response.url == "/"
        cookies = response.cookies
        assert cookies["refreshToken"].value == ""
        assert cookies["sessionid"].value == ""


@pytest.mark.django_db()
class TestImpersonateBeginView:
    @pytest.fixture()
    def staff(self) -> ToolchainUser:
        staff = create_staff(username="john", email="john.clarke@games.com.au", github_user_id="2000")
        return staff

    @pytest.fixture()
    def staff2(self) -> ToolchainUser:
        staff = create_staff(username="gina", email="gina.riley@games.com.au", github_user_id="2001")
        return staff

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        user = create_github_user(
            username="wilson", email="wilson@deadbulder.com.au", github_user_id="94", github_username="wilson"
        )
        return user

    @pytest.fixture()
    def user2(self) -> ToolchainUser:
        user = create_github_user(
            username="frank", email="gdaygdaygday@countryvetcop.tv", github_user_id="87", github_username="frank"
        )
        return user

    @pytest.fixture()
    def session(self, user: ToolchainUser, staff: ToolchainUser) -> ImpersonationSession:
        return ImpersonationSession.objects.create(user_api_id=user.api_id, impersonator_api_id=staff.api_id)

    def test_valid_impersonation_request(self, staff: ToolchainUser, session) -> None:
        client = _get_client(staff)

        response = client.get(f"/impersonate/start/{session.id}/")

        session_after_response = ImpersonationSession.objects.get(id=session.id)
        assert session_after_response.started
        assert response.status_code == 302
        assert response.headers["Location"] == "/"

    def test_reject_starting_already_started_session(self, staff: ToolchainUser, session: ImpersonationSession) -> None:
        client = _get_client(staff)

        session.started = True
        session.save()
        response = client.get(f"/impersonate/start/{session.id}/")
        assert response.status_code == 404

    def test_reject_impersonation_with_non_staff_access(
        self, user2: ToolchainUser, session: ImpersonationSession
    ) -> None:
        client = _get_client(user2)
        response = client.get(f"/impersonate/start/{session.id}/")
        assert response.status_code == 404

    def test_reject_session_started_too_late(self, staff: ToolchainUser, session: ImpersonationSession) -> None:
        client = _get_client(staff)

        session.created_at -= datetime.timedelta(minutes=2, seconds=1)
        session.save()
        response = client.get(f"/impersonate/start/{session.id}/")

        assert response.status_code == 404

    def test_reject_impersonation_by_non_owner(self, staff2: ToolchainUser, session: ImpersonationSession) -> None:
        client = _get_client(staff2)
        response = client.get(f"/impersonate/start/{session.id}/")
        assert response.status_code == 404

    def test_reject_impersonation_of_inactive_user(
        self, staff: ToolchainUser, user: ToolchainUser, session: ImpersonationSession
    ) -> None:
        client = _get_client(staff)
        user.deactivate()
        response = client.get(f"/impersonate/start/{session.id}/")
        assert response.status_code == 403

    def test_reject_impersonation_of_other_staff_member(
        self, client, staff: ToolchainUser, staff2: ToolchainUser, session: ImpersonationSession
    ) -> None:
        client = _get_client(staff)
        session.user_api_id = staff2.api_id
        session.save()
        response = client.get(f"/impersonate/start/{session.id}/")
        assert response.status_code == 403

    def test_reject_impersonation_of_self(self, staff: ToolchainUser, session: ImpersonationSession) -> None:
        client = _get_client(staff)
        session.user_api_id = staff.api_id
        session.save()
        response = client.get(f"/impersonate/start/{session.id}/")
        assert response.status_code == 403


@pytest.mark.django_db()
class TestTOSView:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(
            username="elaine", email="elaine@newyork.com", full_name="Elaine Benes", github_user_id="9901"
        )

    def test_tos_view(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.get("/tos/")
        assert response.status_code == 200
        assert response.template_name == ["users/tos.html"]

    def test_tos_view_no_auth(self, client) -> None:
        response = client.get("/tos/")
        assert response.status_code == 302
        assert response.url == "/accounts/login/?next=/tos/"

    def test_tos_view_tos_already_accepted(self, user: ToolchainUser) -> None:
        accept_tos(user)
        client = _get_client(user)
        response = client.get("/tos/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_tos_view_tos_already_accepted_with_next(self, user: ToolchainUser) -> None:
        accept_tos(user)
        client = _get_client(user)
        response = client.get("/tos/?next=/jerry/no-soup-for-you")
        assert response.status_code == 302
        assert response.url == "/jerry/no-soup-for-you"

    def test_accept_tos(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.post(
            "/tos/",
            data={"tos-version": "hello-newman-2022"},
            HTTP_X_FORWARDED_FOR="35.175.222.211, 127.0.0.1, 10.1.100.87",
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_accept_tos_with_next(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.post(
            "/tos/?next=/crazy/joe/davola",
            data={"tos-version": "hello-newman-2022"},
            HTTP_X_FORWARDED_FOR="35.175.222.211, 127.0.0.1, 10.1.100.87",
        )
        assert response.status_code == 302
        assert response.url == "/crazy/joe/davola"


@pytest.mark.django_db()
class TestNoOrgView:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(
            username="elaine", email="elaine@newyork.com", full_name="Elaine Benes", github_user_id="9901"
        )

    def test_no_org_view(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.get("/org/")
        assert response.status_code == 200
        assert response.context_data["install_github_link"] == "/org/install/"
        assert response.context_data["docs_link"] == "https://docs.toolchain.com/docs/getting-started-with-toolchain"
        assert response.context_data["support_email"] == "support@toolchain.com"
        assert response.template_name == ["users/no-org.html"]
        soup = BeautifulSoup(response.content, "html.parser")
        links = [anchor.attrs["href"] for anchor in soup.select("a")]
        assert "https://docs.toolchain.com/docs/getting-started-with-toolchain" in links

    def test_no_org_view_no_auth(self, client) -> None:
        response = client.get("/org/")
        assert response.status_code == 302
        assert response.url == "/accounts/login/?next=/org/"


@pytest.mark.django_db()
class TestInstallGithubAppView:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(
            username="elaine", email="elaine@newyork.com", full_name="Elaine Benes", github_user_id="9901"
        )

    def test_install_github_app(self, user: ToolchainUser) -> None:
        client = _get_client(user)
        response = client.get("/org/install/")
        assert response.status_code == 302
        assert response.url == "https://no-soup-for-you.jerrt.com/pole/install/"
        cookies = response.cookies
        assert cookies["refreshToken"].value == ""

    def test_install_github_app_no_auth(self, client) -> None:
        response = client.get("/org/install/")
        assert response.status_code == 302
        assert response.url == "/accounts/login/?next=/org/install/"
