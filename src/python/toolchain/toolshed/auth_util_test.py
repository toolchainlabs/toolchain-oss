# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from unittest import mock

import pytest
from django.http import HttpRequest
from django.template.response import TemplateResponse

from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_staff
from toolchain.toolshed.auth_util import check_toolchain_access


@pytest.mark.django_db(transaction=True, databases=["users"])
class TestCheckToolshedAccess:
    @pytest.fixture()
    def fake_request(self) -> HttpRequest:
        req = HttpRequest()
        req.META.update({"SCRIPT_NAME": "", "SERVER_NAME": "no-soup-for-you.seinfeld", "SERVER_PORT": 8111})
        req.method = "GET"
        req.user = mock.MagicMock(is_active=False, is_staff=False)
        return req

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

    def _assert_error_response(self, response) -> None:
        assert isinstance(response, TemplateResponse)
        assert response.status_code == 200
        assert response.context_data["error"] == "Access deined."

    def test_success(self, fake_request: HttpRequest, toolshed_admin: ToolchainUser) -> None:
        resp = check_toolchain_access(None, {"username": "jugdish"}, {"id": 873948}, fake_request)
        assert len(resp) == 2
        assert resp["user"] == toolshed_admin
        assert resp["social"].provider == "github"

    def test_fail_no_user(self, fake_request: HttpRequest, toolshed_admin: ToolchainUser) -> None:
        resp = check_toolchain_access(None, {"username": "jugdish"}, {"id": 63210}, fake_request)
        self._assert_error_response(resp)

        resp = check_toolchain_access(None, {"username": toolshed_admin.username}, {"id": 63210}, fake_request)
        self._assert_error_response(resp)

    def test_fail_inactive_user(self, fake_request: HttpRequest, toolshed_admin: ToolchainUser) -> None:
        ok_resp = check_toolchain_access(
            None,
            {"username": toolshed_admin.username},
            {"id": 873948},
            fake_request,
        )
        assert ok_resp["user"] == toolshed_admin

        toolshed_admin.deactivate()
        resp = check_toolchain_access(
            None,
            {"username": toolshed_admin.username},
            {"id": 873948},
            fake_request,
        )
        self._assert_error_response(resp)

    def test_fail_not_staff_user(self, fake_request: HttpRequest, toolshed_admin: ToolchainUser) -> None:
        toolshed_admin.is_staff = False
        toolshed_admin.save()
        resp = check_toolchain_access(
            None,
            {"username": toolshed_admin.username},
            {"id": 873948},
            fake_request,
        )
        self._assert_error_response(resp)
