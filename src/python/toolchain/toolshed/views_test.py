# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from bs4 import BeautifulSoup
from django.core.signing import get_cookie_signer
from django.test import Client
from jose import jwt

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainError
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user, create_staff
from toolchain.users.models import ImpersonationSession


def _get_client(user: ToolchainUser) -> Client:
    """Sets up a django test client that can pass auth middleware both for django auth and foe 2FA middleware (Duo
    Auth)."""
    client = Client()
    client.force_login(user)
    signer = get_cookie_signer(salt="toolshed" + "no-sup-for-you-come-back-one-year")
    client.cookies["toolshed"] = signer.sign(user.api_id)
    return client


def _add_duo_healthcheck(responses) -> None:
    responses.add(responses.POST, url="https://cosmo.kramer.private/oauth/v1/health_check", json={"stat": "OK"})


def _add_duo_token_check(responses, username: str) -> None:
    now = int(utcnow().timestamp())
    auth_token = jwt.encode(
        claims={
            "aud": "quit-telling-your-st",
            "exp": now + 30,
            "iat": now - 1,
            "iss": "https://cosmo.kramer.private/oauth/v1/token",
            "preferred_username": username,
        },
        key="stay-away-from-the-chicken-bad-chicken-m",
        algorithm="HS512",
    )
    responses.add(
        responses.POST, url="https://cosmo.kramer.private/oauth/v1/token", json={"stat": "OK", "id_token": auth_token}
    )


@pytest.mark.django_db(transaction=True, databases=["users"])
class TestLoginViews:
    def _assert_redirect(self, response, auth_path: str) -> None:
        assert response.status_code == 302
        qp = urlencode({"next": "/"})
        assert response.url == f"/auth/{auth_path}/?{qp}"

    def test_index_no_auth(self, client) -> None:
        client.logout()
        response = client.get("/")
        self._assert_redirect(response, "2fa")

    def test_index_regular_user(self, client) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        client.force_login(user)
        response = client.get("/")
        self._assert_redirect(response, "2fa")

    def test_redirect_to_login_if_cookie_is_missing(self, client) -> None:
        admin = create_staff(username="david", email="puddy@jerrysplace.com", github_user_id="7722")
        client.force_login(admin)
        response = client.get("/")
        self._assert_redirect(response, "2fa")

    def test_logged_in_redirect_to_duo(self, client) -> None:
        admin = create_staff(username="cosmo.kramer", email="cosmos@jerrysplace.com", github_user_id="992")
        client.force_login(admin)
        response = client.get("/auth/login/")
        assert response.status_code == 302
        assert response.url == "/auth/2fa/"

    def test_index(self) -> None:
        admin = create_staff(username="jerry")
        client = _get_client(admin)
        response = client.get("/")
        assert response.status_code == 200
        assert response.template_name == ["admin/toolshed_index.html"]
        links_data = response.context_data["links_data"]
        assert set(links_data) == {"admin", "db_state", "workflow"}
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.title.string == "Toolshed Admin Service"
        pages_links = [anchor["href"] for anchor in soup.select("ul li a")]
        assert pages_links == [
            "db/users/admin/",
            "db/buildsense/admin/",
            "db/scm_integration/admin/",
            "db/oss_metrics/admin/",
            "db/pants_demos/admin/",
            "db/payments/admin/",
            "db/notifications/admin/",
            "db/buildsense/workflow/summary/",
            "db/scm_integration/workflow/summary/",
            "db/oss_metrics/workflow/summary/",
            "db/pants_demos/workflow/summary/",
            "db/payments/workflow/summary/",
            "db/notifications/workflow/summary/",
            "db/users/dbz/",
            "db/buildsense/dbz/",
            "db/scm_integration/dbz/",
            "db/oss_metrics/dbz/",
            "db/pants_demos/dbz/",
            "db/payments/dbz/",
            "db/notifications/dbz/",
        ]


@pytest.mark.django_db(transaction=True, databases=["users"])
class TestDuoViews:
    def test_duo_auth_view(self, client, responses) -> None:
        _add_duo_healthcheck(responses)
        admin = create_staff(username="cosmo.kramer", email="cosmos@jerrysplace.com", github_user_id="992")
        client.force_login(admin)
        response = client.get("/auth/2fa/")
        assert response.status_code == 302
        assert response.url.startswith("https://cosmo.kramer.private/oauth/v1/authorize?")
        url = urlparse(response.url)
        assert url.path == "/oauth/v1/authorize"
        query_params = parse_qs(url.query)
        assert set(query_params.keys()) == {"client_id", "request", "response_type"}
        assert query_params["response_type"] == ["code"]
        assert query_params["client_id"] == ["quit-telling-your-st"]
        token = query_params["request"][0]
        assert jwt.get_unverified_headers(token) == {"typ": "JWT", "alg": "HS512"}
        claims = jwt.get_unverified_claims(token)
        assert set(claims.keys()) == {
            "scope",
            "redirect_uri",
            "client_id",
            "iss",
            "aud",
            "exp",
            "state",
            "response_type",
            "duo_uname",
            "use_duo_code_attribute",
        }
        assert claims["redirect_uri"] == "http://testserver/auth/callback/"
        assert claims["aud"] == "https://cosmo.kramer.private"

    def test_duo_auth_callback_view_missing_query_params(self, client) -> None:
        admin = create_staff(username="cosmo.kramer", email="cosmos@jerrysplace.com", github_user_id="992")
        client.force_login(admin)
        response = client.get("/auth/callback/")
        assert response.status_code == 400

    def test_duo_auth_callback_view(self, client, responses) -> None:
        _add_duo_token_check(responses, username="cosmo.kramer")
        admin = create_staff(username="cosmo.kramer", email="cosmos@jerrysplace.com", github_user_id="992")
        client.force_login(admin)
        session = client.session
        session.update({"state": "soup", "username": "cosmo.kramer"})
        session.save()
        response = client.get("/auth/callback/", data={"duo_code": "bob", "state": "soup"})
        assert response.status_code == 302
        assert response.url == "/"
        assert "toolshed" in response.cookies
        ts_cookie = response.cookies["toolshed"]
        assert ts_cookie["max-age"] == 43200
        assert ts_cookie["httponly"] is True
        assert ts_cookie["domain"] == "jerry.soup.private"  # type: ignore[index]


@pytest.mark.django_db(transaction=True, databases=["users"])
class TestUIImpersonation:
    @property
    def _counter(self) -> int:
        """Temporary fix to overcome fixture reuse across tests."""
        return ToolchainUser.objects.count()

    @pytest.fixture()
    def staff(self) -> ToolchainUser:
        c = self._counter
        return create_staff(username=f"john{c}", email=f"john.clarke{c}@games.com.au", github_user_id=f"2000{c}")

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        c = self._counter
        user = create_github_user(
            username=f"wilson{c}",
            email=f"wilson{c}@deadbulder.com.au",
            github_user_id=f"94{c}",
            github_username=f"wilson{c}",
        )
        return user

    @pytest.fixture()
    def user2(self) -> ToolchainUser:
        c = self._counter
        return create_github_user(
            username=f"frank{c}",
            email=f"gdaygdaygday{c}@countryvetcop.tv",
            github_user_id=f"87{c}",
            github_username=f"frank{c}",
        )

    @pytest.fixture()
    def staff2(self) -> ToolchainUser:
        c = self._counter
        return create_staff(username=f"gina{c}", email=f"gina.riley{c}@games.com.au", github_user_id=f"2001{c}")

    def test_ui_impersonation(self, staff: ToolchainUser, user) -> None:
        client = _get_client(staff)
        response = client.get(f"/impersonate/request/{ user.api_id }/")
        session = ImpersonationSession.objects.get(user_api_id=user.api_id, impersonator_api_id=staff.api_id)
        assert response.status_code == 302
        assert not session.started
        assert response.headers["Location"] == f"https://games.com.au/impersonate/start/{ session.id }/"

    def test_user_can_only_impersonate_one_user_at_a_time(
        self, staff: ToolchainUser, user: ToolchainUser, user2: ToolchainUser
    ) -> None:
        client = _get_client(staff)
        client.get(f"/impersonate/request/{ user.api_id }/")
        session_1 = ImpersonationSession.objects.get(user_api_id=user.api_id, impersonator_api_id=staff.api_id)
        assert session_1.expires_at > utcnow()
        client.get(f"/impersonate/request/{ user2.api_id }/")
        session_1.refresh_from_db()
        session_2 = ImpersonationSession.objects.get(user_api_id=user2.api_id, impersonator_api_id=staff.api_id)

        assert session_1.expires_at <= utcnow()
        assert session_2.expires_at > utcnow()

    def test_user_cannot_request_impersonation_if_has_requested_5_sessions_in_12_hours(
        self, staff: ToolchainUser, user: ToolchainUser
    ) -> None:
        client = _get_client(staff)
        for _ in range(5):
            ImpersonationSession.objects.create(user_api_id=user.api_id, impersonator_api_id=staff.api_id)

        with pytest.raises(ToolchainError):
            client.get(f"/impersonate/request/{ user.api_id }/")

    def test_user_can_request_impersonation_if_5th_session_raised_more_than_12_hours_ago(
        self, staff: ToolchainUser, user: ToolchainUser
    ) -> None:
        client = _get_client(staff)

        for _ in range(4):
            ImpersonationSession.objects.create(user_api_id=user.api_id, impersonator_api_id=staff.api_id)

        ImpersonationSession.objects.create(
            user_api_id=user.api_id,
            impersonator_api_id=staff.api_id,
            created_at=utcnow() - timedelta(hours=12, seconds=1),
        )

        assert (
            ImpersonationSession.objects.filter(user_api_id=user.api_id, impersonator_api_id=staff.api_id).count() == 5
        )

        response = client.get(f"/impersonate/request/{ user.api_id }/")
        sessions = ImpersonationSession.objects.filter(user_api_id=user.api_id, impersonator_api_id=staff.api_id)
        assert sessions.count() == 6
        assert (
            sessions.filter(expires_at__gt=utcnow()).count() == 1
        )  # Should be precisely 1, since other sessions are closed.
        assert response.status_code == 302
        assert "/impersonate/start" in response.headers["Location"]

    def test_ui_impersonation_fails_if_not_logged_in(self, client, staff: ToolchainUser, user: ToolchainUser) -> None:
        response = client.get(f"/impersonate/request/{ user.api_id }/")
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/auth")

    def test_ui_impersonation_fails_on_inactive_user(self, staff: ToolchainUser, user: ToolchainUser) -> None:
        client = _get_client(staff)
        user.deactivate()
        response = client.get(f"/impersonate/request/{ user.api_id }/")
        assert response.status_code == 403

    def test_ui_impersonation_fails_on_staff(self, staff: ToolchainUser, staff2: ToolchainUser) -> None:
        client = _get_client(staff)
        response = client.get(f"/impersonate/request/{ staff2.api_id }/")
        assert (
            ImpersonationSession.objects.filter(user_api_id=staff.api_id, impersonator_api_id=staff2.api_id).count()
            == 0
        )
        assert response.status_code == 403
