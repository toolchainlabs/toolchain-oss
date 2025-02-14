# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from urllib.parse import urlencode

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.signing import get_cookie_signer
from django.http import HttpRequest

from toolchain.django.site.middleware.request_context import save_current_request
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_staff
from toolchain.toolshed.admin_db_context import get_db_context
from toolchain.toolshed.middleware import AdminDbContextMiddleware, AuthMiddleware


class FakeRequest(HttpRequest):
    def __init__(self, path: str, user: ToolchainUser | None = None) -> None:
        super().__init__()
        self.path = path
        self.user = user or AnonymousUser()


@pytest.mark.parametrize(
    ("path", "db_name"),
    [
        ("/db/users/admin/", "users"),
        ("/db/users/login/", "users"),
        ("/db/oss_metrics/admin/", "oss_metrics"),
        ("/db/buildsense/dbz", "buildsense"),
    ],
)
def test_set_db_context(path: str, db_name: str) -> None:
    middleware = AdminDbContextMiddleware(get_response=lambda req: None)
    request = FakeRequest(path)
    save_current_request(request)
    assert middleware.process_request(request) is None
    assert hasattr(request, "_toolchain_db_admin_context") is True
    assert request._toolchain_db_admin_context == db_name  # type: ignore[attr-defined]
    assert get_db_context() == db_name


@pytest.mark.parametrize("path", ["/login/", "/logout/"])
def test_dont_set_db_context(path: str) -> None:
    middleware = AdminDbContextMiddleware(get_response=lambda req: None)
    request = FakeRequest(path)
    save_current_request(request)
    assert middleware.process_request(request) is None
    assert hasattr(request, "_toolchain_db_admin_context") is False
    assert get_db_context() is None


@pytest.mark.django_db(transaction=True, databases=["users"])
class TestAuthMiddleware:
    @pytest.fixture(autouse=True)
    def _init_site(self, client) -> None:
        # Force init of ToolsheAdminSite
        assert client.get("/").status_code == 302

    @pytest.fixture()
    def toolshed_admin(self) -> ToolchainUser:
        # Because of the multi-db setup of Toolshed, pytest-django can't clear DB between runs.
        user = ToolchainUser.objects.filter(username="newman").first()
        if user:
            user.is_active = True
            user.is_staff = True
            user.save()
        else:
            user = create_staff(
                username="newman", email="newman@seinfeld.com", github_user_id="873948", github_username="elaine"
            )
        return user

    @pytest.fixture()
    def middleware(self) -> AuthMiddleware:
        return AuthMiddleware(get_response=lambda req: None)

    @pytest.mark.parametrize("path", ["/auth/login/", "/auth/2fa/", "/auth/callback/"])
    def test_bypass(self, middleware: AuthMiddleware, path: str) -> None:
        assert middleware.process_request(FakeRequest(path)) is None

    @pytest.mark.parametrize("path", ["/db/users/workflow/summary/", "/"])
    def test_redirect_no_user(self, middleware: AuthMiddleware, path: str) -> None:
        response = middleware.process_request(FakeRequest(path))
        assert response is not None
        assert response.status_code == 302
        query = urlencode({"next": path})
        assert response.url == f"/auth/2fa/?{query}"

    @pytest.mark.parametrize("path", ["/db/users/workflow/workexceptions/", "/"])
    def test_redirect_no_cookie(self, middleware: AuthMiddleware, path: str, toolshed_admin: ToolchainUser) -> None:
        response = middleware.process_request(FakeRequest(path, toolshed_admin))
        assert response is not None
        assert response.status_code == 302
        query = urlencode({"next": path})
        assert response.url == f"/auth/2fa/?{query}"

    @pytest.mark.parametrize("path", ["/db/users/workflow/workexceptions/", "/"])
    def test_redirect_with_wrong_cookie(
        self, middleware: AuthMiddleware, path: str, toolshed_admin: ToolchainUser
    ) -> None:
        request = FakeRequest(path, toolshed_admin)
        singer = get_cookie_signer(salt="toolshed" + "no-sup-for-you-come-back-one-year")
        request.COOKIES["toolshed"] = singer.sign("xyz")
        response = middleware.process_request(FakeRequest(path, toolshed_admin))
        assert response is not None
        assert response.status_code == 302
        query = urlencode({"next": path})
        assert response.url == f"/auth/2fa/?{query}"

    @pytest.mark.parametrize("path", ["/db/buildsense/workflow/workexceptions/", "/"])
    def test_redirect_with_cookie(self, middleware: AuthMiddleware, path: str, toolshed_admin: ToolchainUser) -> None:
        request = FakeRequest(path, toolshed_admin)
        singer = get_cookie_signer(salt="toolshed" + "no-sup-for-you-come-back-one-year")
        request.COOKIES["toolshed"] = singer.sign(toolshed_admin.api_id)
        response = middleware.process_request(request)
        assert response is None
