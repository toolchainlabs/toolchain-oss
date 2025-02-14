# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import json

import pytest
from bs4 import BeautifulSoup
from django.test import Client

from toolchain.django.site.models import Customer, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user, create_staff
from toolchain.django.spa.config import StaticContentConfig
from toolchain.servicerouter.services_router_test import setup_impersonation
from toolchain.servicerouter.source_maps_helper_test import create_fake_private_key
from toolchain.users.jwt.utils import get_or_create_refresh_token_for_ui


@pytest.mark.django_db(transaction=True)
class TestFrontendAppView:
    def _create_user(self) -> ToolchainUser:
        customer = Customer.create("festivus", name="Festivus to the rest of us")
        user = create_github_user(username="kramer", email="kramer@jerrysplace.com", github_user_id="44660")
        customer.add_user(user)
        return user

    def _get_client(self) -> tuple[Client, ToolchainUser]:
        user = self._create_user()
        return self._get_client_for_user(user), user

    def _get_staff_client(self) -> tuple[Client, ToolchainUser]:
        customer = Customer.create(slug="sidler", name="The Sidler")
        user = create_staff(username="jerry", email="jerry@jerrysplace.com")
        customer.add_user(user)
        return self._get_client_for_user(user), user

    def _get_client_for_user(self, user: ToolchainUser, impersonation_session_id: str | None = None) -> Client:
        token_str, _ = get_or_create_refresh_token_for_ui(user, impersonation_session_id=impersonation_session_id)
        client = Client()
        client.cookies["refreshToken"] = token_str  # used by users/jwt/middleware.py
        return client

    def _configure_assets_on_cdn(self, settings, commit_sha: str | None = None) -> None:
        settings.STATIC_CONTENT_CONFIG = StaticContentConfig(
            static_url="http://jerry.com/mandelbaum/",
            domains=("jerry.com",),
            version="ovaltine",
            timestamp="jambalaya",
            commit_sha=commit_sha or "shrimp",
            bundles=("runtime", "vendors~main", "main"),
            public_key_id="jackie",
            private_key=create_fake_private_key(),
        )

    def test_authenticated_get_frontend(self) -> None:
        client, user = self._get_client()
        response = client.get("/")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        assert response.template_name == ["servicerouter/index.html"]
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "cinnamon",
                "initialScope": {"user": {"email": "kramer@jerrysplace.com", "id": user.api_id, "username": "kramer"}},
            },
            "assets": {
                "version": "cinnamon",
                "timestamp": "2020-10-22T06:08:57+00:00",
                "disableVersionCheck": False,
                "base_path": "/static/servicerouter/generated/",
            },
        }

        scripts = soup.find_all("script", attrs={"type": "text/javascript"})
        js_bundles = [script["src"] for script in scripts if script.has_attr("src")]
        assert js_bundles == [
            "/static/servicerouter/generated/runtime.js",
            "/static/servicerouter/generated/vendors~main.js",
            "/static/servicerouter/generated/main.js",
        ]

    def test_with_static_assets_version(self, settings) -> None:
        self._configure_assets_on_cdn(settings)
        client, user = self._get_client()
        response = client.get("/")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        assert response.context_data["favicon"] == "/static/favicon.png"
        assert response.template_name == ["servicerouter/index.html"]
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "ovaltine",
                "initialScope": {"user": {"email": "kramer@jerrysplace.com", "id": user.api_id, "username": "kramer"}},
            },
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "assets": {
                "base_path": "/static/servicerouter/generated/",
                "timestamp": "jambalaya",
                "version": "ovaltine",
                "disableVersionCheck": False,
            },
        }

    def _assert_cloudfront_cookies(self, response) -> None:
        assert len(response.cookies) == 3
        assert set(response.cookies.keys()) == {"CloudFront-Expires", "CloudFront-Signature", "CloudFront-Key-Pair-Id"}
        for cookie in response.cookies.values():
            assert cookie["domain"] == "jerry.com"
            assert cookie["httponly"] is True
            assert cookie["secure"] is True
            assert cookie["expires"] == cookie["max-age"] == ""

    def test_with_static_assets_version_and_admin_access(self, settings) -> None:
        self._configure_assets_on_cdn(settings)
        client, user = self._get_staff_client()
        response = client.get("/")
        assert response.status_code == 200
        assert response.context_data["favicon"] == "/static/favicon.png"
        assert response.template_name == ["servicerouter/index.html"]
        self._assert_cloudfront_cookies(response)
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "ovaltine",
                "initialScope": {"user": {"email": "jerry@jerrysplace.com", "id": user.api_id, "username": "jerry"}},
            },
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "assets": {
                "base_path": "/static/servicerouter/generated/",
                "timestamp": "jambalaya",
                "version": "ovaltine",
                "disableVersionCheck": False,
            },
        }

    def test_with_static_assets_version_and_admin_access_and_sentry_test(self, settings) -> None:
        self._configure_assets_on_cdn(settings)
        client, user = self._get_staff_client()
        response = client.get("/?sentry_check=1")
        assert response.status_code == 200
        assert response.context_data["favicon"] == "/static/favicon.png"
        assert response.template_name == ["servicerouter/index.html"]
        self._assert_cloudfront_cookies(response)
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "ovaltine",
                "initialScope": {"user": {"email": "jerry@jerrysplace.com", "id": user.api_id, "username": "jerry"}},
            },
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "flags": {"error_check": True},
            "assets": {
                "base_path": "/static/servicerouter/generated/",
                "timestamp": "jambalaya",
                "version": "ovaltine",
                "disableVersionCheck": False,
            },
        }

    def test_with_static_assets_version_and_commit_sha(self, settings) -> None:
        self._configure_assets_on_cdn(settings, commit_sha="human-fund-money-for-people")
        client, user = self._get_client()
        response = client.get("/")
        assert response.status_code == 200
        assert response.context_data["favicon"] == "/static/favicon.png"
        assert response.template_name == ["servicerouter/index.html"]
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "ovaltine",
                "initialScope": {"user": {"email": "kramer@jerrysplace.com", "id": user.api_id, "username": "kramer"}},
            },
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "assets": {
                "base_path": "/static/servicerouter/generated/",
                "timestamp": "jambalaya",
                "version": "ovaltine",
                "disableVersionCheck": False,
            },
        }

    def test_with_local_dev(self, settings) -> None:
        settings.STATIC_CONTENT_CONFIG = StaticContentConfig.for_test()
        client, user = self._get_client()
        response = client.get("/")
        assert response.status_code == 200
        assert len(response.cookies) == 0
        assert response.context_data["favicon"] == "/static/favicon.png"
        assert response.template_name == ["servicerouter/index.html"]
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "cinnamon",
                "initialScope": {"user": {"email": "kramer@jerrysplace.com", "id": user.api_id, "username": "kramer"}},
            },
            "assets": {
                "version": "cinnamon",
                "timestamp": "2020-10-22T06:08:57+00:00",
                "disableVersionCheck": False,
                "base_path": "/static/servicerouter/generated/",
            },
        }

    def test_unauthenticated_get_frontend(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 302
        assert response.url.startswith("/auth/login/") is True

    def test_assets_versions_view(self, client, settings) -> None:
        settings.STATIC_CONTENT_CONFIG = StaticContentConfig(
            static_url="http://jerry.com/mandelbaum/",
            domains=("jerry.com",),
            version="ovaltine",
            timestamp="jambalaya",
            commit_sha="pole",
            bundles=("runtime", "vendors~main", "main"),
        )
        client.cookies.clear()
        response = client.get("/checksz/versionsz")
        assert response.status_code == 200
        assert response.json() == {"version": "ovaltine", "timestamp": "jambalaya", "disableVersionCheck": False}

    def test_get_frontend_with_impersonation(self) -> None:
        user = self._create_user()
        admin = create_staff("jerry", full_name="Little Jerry Seinfeld")
        session_id, expires_at = setup_impersonation(user=user, admin=admin)
        client = self._get_client_for_user(user, impersonation_session_id=session_id)
        response = client.get("/")

        assert response.status_code == 200
        assert len(response.cookies) == 0
        assert response.template_name == ["servicerouter/index.html"]
        soup = BeautifulSoup(response.content, "html.parser")
        b64_init_data = soup.select("script#app_init_data")[0].string.strip()
        init_data = json.loads(base64.b64decode(b64_init_data))
        assert init_data == {
            "host": "http://testserver",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
            "impersonation": {
                "user_username": "kramer",
                "user_full_name": "",
                "user_api_id": user.api_id,
                "impersonator_username": "jerry",
                "impersonator_full_name": "Little Jerry Seinfeld",
                "impersonator_api_id": admin.api_id,
                "expiry": expires_at.isoformat(),
            },
            "sentry": {
                "dsn": "https://gold.jerry.local",
                "environment": "test",
                "release": "cinnamon",
                "initialScope": {
                    "user": {"id": user.api_id, "email": "kramer@jerrysplace.com", "username": "kramer"},
                    "impersonation": {
                        "user_username": "kramer",
                        "user_full_name": "",
                        "user_api_id": user.api_id,
                        "impersonator_username": "jerry",
                        "impersonator_full_name": "Little Jerry Seinfeld",
                        "impersonator_api_id": admin.api_id,
                        "expiry": expires_at.isoformat(),
                    },
                },
            },
            "assets": {
                "version": "cinnamon",
                "timestamp": "2020-10-22T06:08:57+00:00",
                "disableVersionCheck": False,
                "base_path": "/static/servicerouter/generated/",
            },
        }

        scripts = soup.find_all("script", attrs={"type": "text/javascript"})
        js_bundles = [script["src"] for script in scripts if script.has_attr("src")]
        assert js_bundles == [
            "/static/servicerouter/generated/runtime.js",
            "/static/servicerouter/generated/vendors~main.js",
            "/static/servicerouter/generated/main.js",
        ]


def test_robots_txt(client) -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.content == b"User-agent: *\nDisallow: /"
