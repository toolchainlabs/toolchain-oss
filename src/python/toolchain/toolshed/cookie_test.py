# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.utils.crypto import get_random_string

from toolchain.constants import ToolchainEnv
from toolchain.toolshed.config import AuthCookieConfig
from toolchain.toolshed.cookie import AuthCookie


class TestAuthCookie:
    _TESTS_SALT = "no-sup-for-you-come-back-one-year"  # see; conftest.py

    @pytest.mark.parametrize(("tc_env", "expected_secure"), [("toolchain_dev", ""), ("toolchain_prod", True)])
    def test_store_cookie_in_dev(self, settings, tc_env: str, expected_secure: bool) -> None:
        settings.AUTH_COOKIE_CONFIG = AuthCookieConfig.create(
            ToolchainEnv(tc_env), salt=get_random_string(1024), domain="bookman.cop.private"
        )
        response = HttpResponse()
        AuthCookie.store_cookie(response, "no-soup-for-you")
        cookie = response.cookies["toolshed"]
        assert cookie.key == "toolshed"
        assert cookie.value.partition(":")[0] == "no-soup-for-you"
        assert cookie["max-age"] == 43200  # 12 hours
        assert cookie["domain"] == "bookman.cop.private"
        assert cookie["samesite"] == "Lax"
        assert cookie["httponly"] is True
        assert cookie["secure"] == expected_secure

    def test_load_cookie(self) -> None:
        request = HttpRequest()
        value = signing.get_cookie_signer(salt=f"toolshed{self._TESTS_SALT}").sign("gold jerry, gold!")
        request.COOKIES = {"toolshed": value}
        assert AuthCookie.load_cookie(request) == "gold jerry, gold!"

    def test_load_cookie_unsigned(self) -> None:
        request = HttpRequest()
        request.COOKIES = {"toolshed": "gold jerry, gold!"}
        assert AuthCookie.load_cookie(request) is None

    def test_load_cookie_invalid_signature_salt(self) -> None:
        request = HttpRequest()
        value = signing.get_cookie_signer(salt="toolshed" + "tinsel").sign("gold jerry, gold!")
        request.COOKIES = {"toolshed": value}
        assert AuthCookie.load_cookie(request) is None

    def test_load_cookie_other_cookie(self) -> None:
        request = HttpRequest()
        request.COOKIES = {"toolchain": "gold jerry, gold!"}
        assert AuthCookie.load_cookie(HttpRequest()) is None

    def test_load_cookie_no_cookies(self) -> None:
        assert AuthCookie.load_cookie(HttpRequest()) is None
