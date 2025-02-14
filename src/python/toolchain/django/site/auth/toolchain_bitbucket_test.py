# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from unittest import mock

import pytest

from toolchain.django.site.auth.toolchain_bitbucket import ToolchainBitbucketOAuth2
from toolchain.users.ui.views_test import load_fixture


@pytest.mark.django_db()
class TestToolchainBitbucketOAuth2:
    @pytest.fixture()
    def bitbucket_backend(self) -> ToolchainBitbucketOAuth2:
        req = mock.MagicMock()
        return ToolchainBitbucketOAuth2.for_request(req, redirect_uri="")

    def _add_response(self, responses, path: str, fixture_name: str) -> None:
        responses.add(responses.GET, f"https://api.bitbucket.org/2.0/{path}", json=load_fixture(fixture_name))

    def test_name(self, bitbucket_backend: ToolchainBitbucketOAuth2) -> None:
        assert bitbucket_backend.name == "bitbucket"

    def test_user_data(self, responses, bitbucket_backend: ToolchainBitbucketOAuth2) -> None:
        self._add_response(responses, "user/emails", "bitbucket_user_emails")
        self._add_response(responses, "user", "bitbucket_user")
        self._add_response(responses, "workspaces", "bitbucket_workspaces")
        user_data = bitbucket_backend.user_data("uncle-leo")
        assert len(responses.calls) == 3
        assert responses.calls[1].request.url == "https://api.bitbucket.org/2.0/user"
        assert responses.calls[0].request.url == "https://api.bitbucket.org/2.0/user/emails"
        assert responses.calls[2].request.url == "https://api.bitbucket.org/2.0/workspaces"
        for call in responses.calls:
            assert call.request.method == "GET"
            assert "Authorization" in call.request.headers
            assert call.request.headers["Authorization"] == "Bearer uncle-leo"

        assert user_data == {
            "username": "jerry",
            "display_name": "Jerry Seinfeld",
            "has_2fa_enabled": None,
            "links": {
                "hooks": {
                    "href": "https://api.bitbucket.org/2.0/users/%7B6ae3c307-ae59-4135-9c72-ea19ffffffff%7D/hooks"
                },
                "self": {"href": "https://api.bitbucket.org/2.0/users/%7B6ae3c307-ae59-4135-9c72-ea19ffffffff%7D"},
                "repositories": {
                    "href": "https://api.bitbucket.org/2.0/repositories/%7B6ae3c307-ae59-4135-9c72-ea19ffffffff%7D"
                },
                "html": {"href": "https://bitbucket.org/%7B6ae3c307-ae59-4135-9c72-ea19ffffffff%7D/"},
                "avatar": {"href": "https://secure.gravatar.com/jerrys.jpg"},
                "snippets": {
                    "href": "https://api.bitbucket.org/2.0/snippets/%7B6ae3c307-ae59-4135-9c72-ea19ffffffff%7D"
                },
            },
            "nickname": "Jagdish",
            "account_id": "6059303e630024006f000000",
            "created_on": "2011-12-31T16:12:40.159310+00:00",
            "is_staff": False,
            "location": None,
            "account_status": "active",
            "type": "user",
            "uuid": "{6ae3c307-ae59-4135-9c72-ea19ffffffff}",
            "organization_names": frozenset(("newman",)),
            "verified_emails": frozenset(("jerry@seinfeld.com",)),
            "email": "jerry@seinfeld.com",
        }
