# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import time
import zlib
from collections import defaultdict
from io import BytesIO

import httpx
import pkg_resources
import pytest
from django.test import override_settings
from django.test.client import MULTIPART_CONTENT
from django.urls import resolve
from django.utils.http import http_date, parse_http_date

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user, create_staff
from toolchain.django.spa.config import StaticContentConfig
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.users.jwt.middleware_test import generate_access_token_header
from toolchain.users.models import ImpersonationSession
from toolchain.util.constants import REQUEST_ID_HEADER
from toolchain.util.test.multipart_parser import parse_multipart_request
from toolchain.util.test.util import convert_headers_to_wsgi


def setup_impersonation(user: ToolchainUser, admin: ToolchainUser) -> tuple[str, datetime.datetime]:
    session_id = ImpersonationSession.create_and_return_id(user_api_id=user.api_id, impersonator_api_id=admin.api_id)
    session = ImpersonationSession.get_fresh_session_for_impersonator_or_none(session_id, admin.api_id)
    assert session is not None
    session.start()
    return session_id, session.expires_at


@pytest.mark.django_db()
class TestServiceRouterProxy:
    _FAKE_VALUES = {
        "pk": "gold",
        "repo_slug": "shirt",
        "customer_slug": "nbc",
        "token_id": "29XahgkTbF3wfdmxVn6SvQ",
        "token": "yamahama",
        "uidb64": "sixty88",
        "customer_pk": "seinfeld",
        "user_api_id": "JFKDFJKS948FDSF",
        "name": "kramerica",
        "packagerepo_name": "kramerica-industries",
        "project_name": "blubber",
        "version": "0.0.1",
        "release_version": "0.0.2",
        "filename": "foo-0-0-2.whl",
        "run_id": "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c",
        "artifact_id": "jerry_seinfeld.txt",
        "session_id": "its_about_100_metres",
    }
    _APPS_FOR_SERVICE = {
        "users/ui": USERS_DB_DJANGO_APPS + ("toolchain.workflow.apps.WorkflowAppConfig",),
        "users/api": USERS_DB_DJANGO_APPS + ("toolchain.workflow.apps.WorkflowAppConfig",),
        "dependency/api": (
            "toolchain.dependency.apps.DependencyAPIAppConfig",
            "toolchain.django.webresource.apps.WebResourceAppConfig",
            "toolchain.packagerepo.pypi.apps.PackageRepoPypiAppConfig",
        ),
        "buildsense/api": (
            "toolchain.buildsense.apps.BuildSenseAppConfig",
            "toolchain.buildsense.ingestion.apps.BuildDataIngestionAppConfig",
            "toolchain.workflow.apps.WorkflowAppConfig",
        ),
    }

    @pytest.fixture()
    def routes(self) -> dict:
        return json.loads(pkg_resources.resource_string(__name__, "service_routes.json"))["routes"]

    @pytest.fixture()
    def routes_by_service(self, routes: dict) -> dict:
        routes_by_service = defaultdict(list)
        for route in routes:
            routes_by_service[route["service"]].append(route)
        return routes_by_service

    def test_duplicates(self, routes) -> None:
        all_sources = {route["source"] for route in routes}
        assert len(all_sources) == len(routes)

    def test_urls_routes(self, settings, routes_by_service: dict) -> None:
        for service, routes in routes_by_service.items():
            service_path = service.replace("/", ".")
            root_url_conf = f"toolchain.service.{service_path}.urls"
            with override_settings(INSTALLED_APPS=self._APPS_FOR_SERVICE[service]):
                for route in routes:
                    try:
                        url = route["target"]
                        pass_args = route.get("pass_args")
                        if pass_args:
                            url = url.format(**{pa: self._FAKE_VALUES[pa] for pa in pass_args})
                        match = resolve(url, urlconf=root_url_conf)
                        if route["name"]:
                            assert match.view_name == route["name"]
                    except BaseException:
                        print(f"Failed for service: {service}, route: {route}")
                        raise

    def test_call_downstream_service(self, client, settings, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url="http://localhost:9010/auth/login/", text="No soup for you")

        settings.STATIC_CONTENT_CONFIG = StaticContentConfig.for_test()
        response = client.get("/auth/login/")
        assert response.status_code == 200
        assert response.has_header("X-SPA-Version") is False
        assert response.content == b"No soup for you"
        assert httpx_mock.get_request() is not None

    def test_call_downstream_service_with_url_args(self, client, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9042/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/?david=puddy",
            text="Excruciating minutia",
        )

        response = client.get("/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/", data={"david": "puddy"})
        assert response.status_code == 200
        assert response.content == b"Excruciating minutia"
        request = httpx_mock.get_request()
        assert request.url.query == b"david=puddy"

    def test_call_downstream_service_with_auth(self, client, httpx_mock) -> None:
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer", full_name="C. Kramer")
        auth_header = generate_access_token_header(user, audience=AccessTokenAudience.FRONTEND_API)
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9042/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/?david=puddy",
            text="Excruciating minutia",
        )

        response = client.get(
            "/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/",
            data={"david": "puddy"},
            HTTP_AUTHORIZATION=auth_header,
        )
        assert response.status_code == 200
        assert response.content == b"Excruciating minutia"
        request = httpx_mock.get_request()

        assert request.url.query == b"david=puddy"
        assert request.headers["Remote-User"] == f"cosmo/{user.api_id}"
        toolchain_auth = json.loads(request.headers["X-Toolchain-Internal-Auth"])
        assert len(toolchain_auth) == 2
        assert toolchain_auth == {
            "user": {"api_id": user.api_id},
            "claims": {
                "user_api_id": user.api_id,
                "username": "cosmo",
                "audience": ["frontend"],
                "token_type": "access",
                "token_id": None,
                "impersonation_session_id": None,
            },
        }

    def _get_cookie_header(
        self,
        name: str,
        value: str,
        max_age: datetime.timedelta,
        is_secure: bool = False,
        http_only: bool = False,
    ) -> tuple[str, str]:
        max_age_secs = int(max_age.total_seconds())
        expires = http_date(time.time() + max_age_secs)
        value = f"{name}={value}; expires={expires}; Max-Age={max_age_secs}; Path=/; SameSite=Lax"
        if http_only:
            value = f"{value}; HttpOnly"
        if is_secure:
            value = f"{value}; Secure"
        return "Set-Cookie", value

    def _assert_cookie(self, cookie, expiration_days: int, secure: bool, http_only: bool) -> None:
        now = utcnow()
        cookie_dict = dict(cookie.items())
        expected_expiration_ts = int((now + datetime.timedelta(days=expiration_days)).timestamp())
        assert parse_http_date(cookie_dict.pop("expires")) == pytest.approx(expected_expiration_ts, rel=2)
        # Django adds a second to max-age
        expected_max_age = int(1 + expected_expiration_ts - now.timestamp())
        assert cookie_dict.pop("max-age") == pytest.approx(expected_max_age, rel=2)
        assert cookie_dict == {
            "path": "/",
            "comment": "",
            "domain": "",
            "secure": True if secure else "",
            "httponly": True if http_only else "",
            "version": "",
            "samesite": "Lax",
        }

    def test_call_downstream_service_with_cookie(self, client, httpx_mock) -> None:
        cookies_header = self._get_cookie_header("uncle_leo", "hello", datetime.timedelta(days=8))
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9010/auth/login/",
            text="I don't want to be a pirate",
            headers=[cookies_header],
        )

        response = client.get("/auth/login/")
        assert httpx_mock.get_request() is not None
        assert response.status_code == 200
        assert response.content == b"I don't want to be a pirate"
        assert response.has_header("X-SPA-Version") is False
        assert response.has_header("Set-Cookie") is False
        assert len(response.cookies) == 1
        cookie = response.cookies["uncle_leo"]
        assert cookie.value == "hello"
        self._assert_cookie(cookie, expiration_days=8, secure=False, http_only=False)

    def test_call_downstream_service_with_multiple_cookies(self, client, httpx_mock) -> None:
        cookies_header_1 = self._get_cookie_header("uncle_leo", "hello", datetime.timedelta(days=3))
        cookies_header_2 = self._get_cookie_header("soup", "bisque", datetime.timedelta(days=30), http_only=True)
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9010/auth/login/",
            text="I don't want to be a pirate",
            headers=[cookies_header_1, cookies_header_2],
        )

        response = client.get("/auth/login/")
        assert httpx_mock.get_request() is not None
        assert response.status_code == 200
        assert response.content == b"I don't want to be a pirate"
        assert response.has_header("X-SPA-Version") is False
        assert response.has_header("Set-Cookie") is False
        assert len(response.cookies) == 2

        cookie_1 = response.cookies["uncle_leo"]
        assert cookie_1.value == "hello"
        self._assert_cookie(cookie_1, expiration_days=3, secure=False, http_only=False)

        cookie_2 = response.cookies["soup"]
        assert cookie_2.value == "bisque"
        self._assert_cookie(cookie_2, expiration_days=30, secure=False, http_only=True)

    def test_call_downstream_service_with_multiple_cookies_secure(self, client, httpx_mock) -> None:
        cookies_header_1 = self._get_cookie_header("uncle_leo", "hello", datetime.timedelta(days=3))
        cookies_header_2 = self._get_cookie_header(
            "soup", "bisque", datetime.timedelta(days=30), is_secure=True, http_only=True
        )
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9010/auth/login/",
            text="I don't want to be a pirate",
            headers=[cookies_header_1, cookies_header_2],
        )

        response = client.get("/auth/login/")
        assert httpx_mock.get_request() is not None
        assert response.status_code == 200
        assert response.content == b"I don't want to be a pirate"

        assert response.has_header("Set-Cookie") is False
        assert len(response.cookies) == 2

        cookie_1 = response.cookies["uncle_leo"]
        assert cookie_1.value == "hello"
        self._assert_cookie(cookie_1, expiration_days=3, secure=False, http_only=False)

        cookie_2 = response.cookies["soup"]
        assert cookie_2.value == "bisque"
        self._assert_cookie(cookie_2, expiration_days=30, secure=True, http_only=True)

    def test_call_downstream_service_with_multiple_cookies_with_deletions(self, client, httpx_mock) -> None:
        cookies_header = self._get_cookie_header("uncle_leo", "hello", datetime.timedelta(days=8), http_only=False)
        deleted_cookie_header = (
            "Set-Cookie",
            'soup=" "; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Lax',
        )
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9010/auth/complete/github/",
            content="I don't want to be a pirate",
            headers=[cookies_header, deleted_cookie_header],
        )

        response = client.get("/auth/complete/github/")
        assert httpx_mock.get_request() is not None
        assert response.status_code == 200
        assert response.content == b"I don't want to be a pirate"

        # Django doesn't convert cookies to headers in tests so we don't expect those headers (It is done in WSGIHandler which doesn't run in tests).
        assert response.has_header("Set-Cookie") is False
        assert len(response.cookies) == 2

        cookie_1 = response.cookies["uncle_leo"]
        assert cookie_1.value == "hello"
        self._assert_cookie(cookie_1, expiration_days=8, secure=False, http_only=False)
        cookie_2 = response.cookies["soup"]
        assert cookie_2.value == ""

    def test_post_downstream_service_with_single_small_file(self, client, httpx_mock) -> None:
        fp = BytesIO(zlib.compress(b"jerry berry merry derry" * 200))
        httpx_mock.add_response(
            method="POST", url="http://localhost:9042/api/v1/repos/seinfeld/jerry/buildsense/batch/", json={"ok": "yes"}
        )
        response = client.post("/api/v1/repos/seinfeld/jerry/buildsense/batch/", {"some_file.bin": fp})
        assert response.status_code == 200
        assert response.json() == {"ok": "yes"}

        self._assert_file_upload_request(httpx_mock.get_request())

    def test_patch_downstream_service_with_single_small_file(self, client, httpx_mock, settings) -> None:
        # Using a small value to not allow the request body to processed, since we want to ensure that the multipart parser is triggered here.
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 10
        fp = BytesIO(zlib.compress(b"jerry berry merry derry" * 200))
        httpx_mock.add_response(
            method="PATCH",
            url="http://localhost:9042/api/v1/repos/seinfeld/jerry/buildsense/batch/",
            json={"ok": "yes"},
        )
        # Not using client.patch since it won't encode file data as multipart.
        patch_data = client._encode_data(data={"some_file.bin": fp}, content_type=MULTIPART_CONTENT)
        response = client.generic(
            method="PATCH",
            path="/api/v1/repos/seinfeld/jerry/buildsense/batch/",
            data=patch_data,
            content_type=MULTIPART_CONTENT,
            secure=False,
        )
        assert response.status_code == 200
        assert response.json() == {"ok": "yes"}
        self._assert_file_upload_request(httpx_mock.get_request())

    def _assert_file_upload_request(self, request):
        assert request.headers["Content-Length"] == "249"
        post_data, files_data = parse_multipart_request(request)
        assert len(post_data) == 0
        assert len(files_data) == 1
        assert "some_file.bin" in files_data
        fd = zlib.decompress(files_data["some_file.bin"].raw)
        assert fd == b"jerry berry merry derry" * 200

    def test_get_spa_version_header_no_reload(self, client, httpx_mock, settings) -> None:
        settings.STATIC_CONTENT_CONFIG = StaticContentConfig.for_test()
        httpx_mock.add_response(
            method="GET", url="http://localhost:9011/api/v1/users/me/", json={"bakery": "cinnamon-babka"}
        )

        response = client.get(
            "/api/v1/users/me/",
            HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/82.0",
        )
        assert response.status_code == 200
        assert response.has_header("X-SPA-Version") is True
        assert json.loads(response["X-SPA-Version"]) == {
            "version": "cinnamon",
            "timestamp": "2020-10-22T06:08:57+00:00",
            "no_reload": True,
        }
        assert response.json() == {"bakery": "cinnamon-babka"}
        assert httpx_mock.get_request() is not None

    def test_get_spa_version_header(self, client, httpx_mock, settings, monkeypatch) -> None:
        settings.STATIC_CONTENT_CONFIG = StaticContentConfig.for_test()
        fake_start_time = time.time() - datetime.timedelta(hours=2).total_seconds()
        monkeypatch.setattr("toolchain.servicerouter.services_router.process_start_time", fake_start_time)
        httpx_mock.add_response(
            method="GET", url="http://localhost:9011/api/v1/users/me/", json={"bakery": "cinnamon-babka"}
        )

        response = client.get(
            "/api/v1/users/me/",
            HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/82.0",
        )
        assert response.status_code == 200
        assert response.has_header("X-SPA-Version") is True
        assert json.loads(response["X-SPA-Version"]) == {
            "version": "cinnamon",
            "timestamp": "2020-10-22T06:08:57+00:00",
        }
        assert response.json() == {"bakery": "cinnamon-babka"}
        assert httpx_mock.get_request() is not None

    def test_patch_upstream(self, httpx_mock, client) -> None:
        httpx_mock.add_response(
            method="PATCH", url="http://localhost:9011/api/v1/users/eFp6DCh2TCBwjh7QT7mcsP/", json={"update": "ok"}
        )
        response = client.patch(
            "/api/v1/users/eFp6DCh2TCBwjh7QT7mcsP/",
        )
        assert response.status_code == 200
        assert response.json() == {"update": "ok"}
        assert httpx_mock.get_request() is not None

    def test_proxy_invalid_user_agent(self, httpx_mock, client) -> None:
        httpx_mock.add_response(
            method="GET", url="http://localhost:9010/auth/login/", content=b"<html><body>no soup for you<body></html>"
        )
        headers = {
            "User-Agent": "domainjäger",
            "X-Amzn-Trace-Id": "Root=1-60fb4a0e-18f7496049cc3a1210ea7c5a",
            "X-Forwarded-For": "65.21.51.3, 10.1.111.232, 127.0.0.1",
            REQUEST_ID_HEADER: "eacb41af72d480a2fe64eda511ab9f66",
        }

        response = client.get("/auth/login/", **convert_headers_to_wsgi(headers))
        assert response.status_code == 200
        assert response.content == b"<html><body>no soup for you<body></html>"
        headers = httpx_mock.get_request().headers
        assert dict(headers) == {
            "host": "localhost:9010",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate",
            "connection": "keep-alive",
            "user-agent": "domainjäger",
            "x-amzn-trace-id": "Root=1-60fb4a0e-18f7496049cc3a1210ea7c5a",
            "x-forwarded-for": "65.21.51.3, 10.1.111.232, 127.0.0.1, 127.0.0.1",
            "x-request-id": "eacb41af72d480a2fe64eda511ab9f66",
            "x-forwarded-proto": "http",
            "x-forwarded-host": "testserver",
        }

    def test_call_downstream_service_with_impersonation(self, client, httpx_mock) -> None:
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer", full_name="C. Kramer")
        admin = create_staff("jerry", full_name="Jerry Seinfeld")
        session_id, session_expiration = setup_impersonation(user=user, admin=admin)
        auth_header = generate_access_token_header(
            user, audience=AccessTokenAudience.FRONTEND_API, toolchain_impersonation_session=session_id
        )
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:9042/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/?david=puddy",
            text="Excruciating minutia",
        )

        response = client.get(
            "/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/",
            data={"david": "puddy"},
            HTTP_AUTHORIZATION=auth_header,
        )
        assert response.status_code == 200
        assert response.content == b"Excruciating minutia"
        request = httpx_mock.get_request()

        assert request.url.query == b"david=puddy"
        assert request.headers["Remote-User"] == f"cosmo/{user.api_id}"
        toolchain_auth = json.loads(request.headers["X-Toolchain-Internal-Auth"])
        assert len(toolchain_auth) == 3
        assert toolchain_auth == {
            "user": {"api_id": user.api_id},
            "claims": {
                "user_api_id": user.api_id,
                "username": "cosmo",
                "audience": ["frontend"],
                "token_type": "access",
                "token_id": None,
                "impersonation_session_id": session_id,
            },
            "impersonation": {
                "expiry": session_expiration.isoformat(),
                "impersonator_full_name": "Jerry Seinfeld",
                "impersonator_username": "jerry",
                "impersonator_api_id": admin.api_id,
                "user_full_name": "C. Kramer",
                "user_username": "cosmo",
                "user_api_id": user.api_id,
            },
        }

    def test_call_downstream_service_with_invalid_impersonation_not_started(self, client) -> None:
        user = create_github_user("cosmo", github_user_id="71123", github_username="kramer", full_name="C. Kramer")
        admin = create_staff("jerry")
        session_id = ImpersonationSession.create_and_return_id(
            user_api_id=user.api_id, impersonator_api_id=admin.api_id
        )
        auth_header = generate_access_token_header(
            user, audience=AccessTokenAudience.FRONTEND_API, toolchain_impersonation_session=session_id
        )
        response = client.get(
            "/api/v1/repos/seinfeld/jerry/buildsense/no_soup_for_you/",
            data={"david": "puddy"},
            HTTP_AUTHORIZATION=auth_header,
        )
        assert response.status_code == 403
        assert (
            response.content
            == b'\n<!doctype html>\n<html lang="en">\n<head>\n  <title>403 Forbidden</title>\n</head>\n<body>\n  <h1>403 Forbidden</h1><p></p>\n</body>\n</html>\n'
        )

    def test_call_downstream_service_timeout(self, client, settings, httpx_mock) -> None:
        httpx_mock.add_exception(
            httpx.ReadTimeout("no soup for you"),
            method="GET",
            url="http://localhost:9042/api/v1/repos/toolchainlabs/toolchain/builds/pants_run_2021_12_1/artifacts/test_543ac7682493c7af_artifacts.json/",
        )
        settings.STATIC_CONTENT_CONFIG = StaticContentConfig.for_test()
        response = client.get(
            "/api/v1/repos/toolchainlabs/toolchain/builds/pants_run_2021_12_1/artifacts/test_543ac7682493c7af_artifacts.json/"
        )
        assert response.status_code == 503
        assert response.json() == {"error": "transient", "error_type": "DownstreamServiceTimeoutError"}
        assert httpx_mock.get_request() is not None
