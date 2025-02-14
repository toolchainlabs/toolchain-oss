# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
import time
from http.cookiejar import Cookie, CookieJar
from http.cookies import Morsel, SimpleCookie
from urllib.parse import urljoin

import httpx
import pkg_resources
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.urls import path, re_path
from djproxy.headers import HeaderDict
from djproxy.request import DownstreamRequest
from djproxy.views import HttpProxy

from toolchain.base.toolchain_error import ToolchainTransientError
from toolchain.config.endpoints import get_gunicorn_service_endpoint
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.utils.request_utils import load_post_and_files
from toolchain.util.constants import REQUEST_ID_HEADER

_logger = logging.getLogger(__name__)


process_start_time = time.time()
PREVENT_RELOAD_THRESHOLD_SEC = 60


class DownstreamServiceTimeoutError(ToolchainTransientError):
    def __init__(self, url: str, service: str, msg: str) -> None:
        self._url = url
        self._service = service
        super().__init__(msg)

    @property
    def url(self) -> str:
        return self._url

    @property
    def service(self) -> str:
        return self._service


def _add_cookies(response: HttpResponse, cookies: tuple[Cookie, ...]) -> None:
    for cookie in cookies:
        expires = datetime.datetime.fromtimestamp(cookie.expires, datetime.timezone.utc) if cookie.expires else None
        response.set_cookie(
            key=cookie.name,
            value=cookie.value,
            path=cookie.path,
            expires=expires,
            domain=cookie.domain if cookie.domain_specified else None,
            secure=cookie.secure,
            httponly=cookie.has_nonstandard_attr("HttpOnly"),
            samesite=cookie.get_nonstandard_attr("SameSite") or None,
        )


def load_cookie(value: bytes) -> Morsel:
    cookies: SimpleCookie = SimpleCookie()
    cookies.load(value.decode())
    return next(iter(cookies.values()))


def _convert_cookie_headers(response: httpx.Response) -> tuple[CookieJar, list[str]]:
    cookies_to_delete = []
    new_headers = []
    for name, value in response.headers.raw:
        if name == b"Set-Cookie":
            cookie = load_cookie(value)
            if not cookie.value or not cookie.value.strip():
                cookies_to_delete.append(cookie.key)
                continue
        new_headers.append((name.decode(), value.decode()))
    # Using a fake/temp response object to leverage cookie parsing logic
    fake_response = httpx.Response(status_code=200, request=response.request, headers=httpx.Headers(new_headers))
    cookies = fake_response.cookies.jar
    return cookies, cookies_to_delete


class ToolchainHttpProxy(HttpProxy):
    view_type = "app"
    retries = 0
    pass_args: list[str] = []
    service_name = None
    # Avoid ignoring the host header
    ignored_request_headers = [
        "Content-Length",
        "Keep-Alive",
        "Connection",
        "Expect",
        "Upgrade",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Internally we don't use HTTPS (yet)
        self._client = httpx.Client(transport=httpx.HTTPTransport(retries=self.retries))

    def proxy(self):
        """Retrieve the upstream content and build an HttpResponse."""
        request = self.request
        wsgi_request = request._request if isinstance(request, DownstreamRequest) else request
        if not isinstance(wsgi_request, WSGIRequest):
            # TODO: This should be an error, since we fully expect wsgi_request to be WSGIRequest
            # But for now we do a soft check and we will do a tigher check after making sure we don't hit this code path.
            _logger.warning(f"unexpected_request_type {type(wsgi_request)} {type(request)}")
        if self.is_deprecated:
            _logger.info(f"deprecated path used:{self.name}  path={wsgi_request.path} ")
        headers = request.headers.filter(self.ignored_request_headers)
        encoded_headers = {name: value.encode() for name, value in headers.items()}
        qs = request.query_string if self.pass_query_string else ""
        load_post_and_files(wsgi_request)  # Allows multipart uploads in PATCH requests (in addition to POST)
        request_files = wsgi_request.FILES
        if request_files:
            payload_kwargs = {"files": dict(request_files.items())}
            del encoded_headers["Content-Type"]  # let requests library re-create this header.
            if self.disable_request_files_close:
                # Under tests, django will call request.close (via HttpResponse._resource_closers) which is problematic
                # Since it will close the underlying file object (which is stored in httpx-mock requests) and will prevent us
                # from reading it and parsing it under in the test to make sure multipart upload is being proxies properly.
                wsgi_request._files.clear()
        elif wsgi_request.body:
            payload_kwargs = {"data": wsgi_request.body}
        else:
            payload_kwargs = {}
        request_kwargs = self.middleware.process_request(
            self,
            request,
            method=request.method,
            url=self.proxy_url,
            headers=encoded_headers,
            params=qs,
            timeout=self.timeout,
            **payload_kwargs,
        )

        try:
            result = self._client.request(**request_kwargs)
        except httpx.TimeoutException as error:
            req = error.request
            _logger.warning(f"Timeout error calling: service={self.service_name} url={req.url=} {error!r}")
            raise DownstreamServiceTimeoutError(url=req.url, service=self.service_name, msg=str(error))
        # urllib3 (which is used by the requests library) will merge headers with the same key.
        # This specifically impacts cookies and merges them into a single header.
        # https://github.com/urllib3/urllib3/blob/46fc29d5108553a58cc14d28e73443e864be76c2/src/urllib3/_collections.py#L130-L135
        # This means that if we get more than one cookie from the downstream service we call to here,
        # those will get merged and sent as a single Set-Cookie header via the django http response.
        # This in turn, means that the browser, will only see one cookie and not all of them,
        # since the browser expects a single cookie in each Set-Cookie header.
        # So we create a copy of the cookies and then remove them from the response we got from the downstream service.
        # We add those cookies back to the response before returning and django does the right thing (in the wsgi handler)
        # and converts each cookie to its own Set-Cookie header.
        cookies, cookies_to_delete = _convert_cookie_headers(result)
        if cookies or cookies_to_delete:
            del result.headers["Set-Cookie"]
        # TODO: We should handle connection errors here instead  of letting them become unhandled exceptions and HTTP 500 errors.
        # But during the beta, we don't want to silence those errors (Until we can properly alert on those errors happening otherwise).
        response = HttpResponse(result.content, status=result.status_code)

        # Attach forwardable headers to response
        forwardable_headers = HeaderDict(result.headers).filter(self.ignored_upstream_headers)
        for header, value in forwardable_headers.items():
            response[header] = value

        final_response = self.middleware.process_response(self, self.request, result, response)
        _add_cookies(response=final_response, cookies=cookies)
        for cookie_name in cookies_to_delete:
            final_response.delete_cookie(cookie_name)
        return final_response

    @property
    def proxy_url(self):
        base_url = self.base_url
        if self.pass_args:
            url = base_url.format(**{pa: self.kwargs[pa] for pa in self.pass_args})
        else:
            url = urljoin(base_url, self.kwargs.get("url", ""))
        return url


def generate_proxy(
    *, route: dict[str, str], timeout: int, proxy_middlewares: list[str], is_deprecated: bool, name: str
):
    service = route["service"]
    disable_request_files_close = getattr(settings, "IS_TOOLCHAIN_DJANGO_TESTS", False)
    service_endpoint = get_gunicorn_service_endpoint(settings, service)
    base_url = urljoin(service_endpoint, route["target"])
    proxy_cbv = type(
        "ProxyClass",
        (ToolchainHttpProxy,),
        {
            "service_name": service,
            "base_url": base_url,
            "pass_args": route.get("pass_args") or [],
            "reverse_urls": [],
            "retries": 2,  # we can customize in service_routes.json per endpoint if we need to (similar to timeout)
            "proxy_middleware": proxy_middlewares,
            "timeout": timeout,
            "disable_request_files_close": disable_request_files_close,
            "is_deprecated": is_deprecated,
            "name": name,
        },
    )
    proxy_view_func = proxy_cbv.as_view()  # type: ignore[attr-defined]
    proxy_view_func.csrf_exempt = route.get("csrf_exempt", True)
    return proxy_view_func


def get_routing_urls():
    all_urls = []
    routes = json.loads(pkg_resources.resource_string(__name__, "service_routes.json"))["routes"]
    proxy_middlewares = ["toolchain.servicerouter.services_router.ServiceRouterRequestMiddleware"]
    # when running locally, we want a longer timeout to allow using breakpoints in downstream services
    # w/o service router downstream connections timing out.
    override_timeout = 0 if settings.IS_RUNNING_ON_K8S else 300
    for route in routes:
        timeout = override_timeout or route.get("timeout") or 3  # default to a 3 seconds timeout
        name = route["name"]
        is_deprecated = route.get("deprecated", False)
        proxy = generate_proxy(
            route=route, timeout=timeout, proxy_middlewares=proxy_middlewares, is_deprecated=is_deprecated, name=name
        )
        url_func = path if route.get("use_path") is True else re_path
        all_urls.append(url_func(route["source"], proxy, name=name))
    return all_urls


class ServiceRouterRequestMiddleware:
    def __init__(self) -> None:
        cfg = settings.STATIC_CONTENT_CONFIG
        self._spa_version_info: dict | None = None
        if not cfg.is_local:
            self._spa_version_info = {"version": cfg.version, "timestamp": cfg.timestamp}
            self._spa_version_info_json = json.dumps(self._spa_version_info)

    def process_request(self, proxy, request, **kwargs):
        headers = kwargs["headers"]
        headers.update(
            {
                "X-Forwarded-Proto": "https" if request.is_secure() else "http",
                "X-Forwarded-Host": request.get_host(),
                "X-Forwarded-For": request.x_forwarded_for,
                REQUEST_ID_HEADER: request.request_id,
            }
        )
        # Eventually, what we want to do here is to take the cookie (session ID) or JWT token (from the header)
        # and call the users/api service to run the auth logic checks and return json data which we then stick into
        # this header for the downstream services to use.
        # This way we can isolate access to the users DB only to the users/X services.
        user = request.toolchain_user
        if user:
            claims = request.toolchain_jwt_claims
            impersonation = request.toolchain_impersonation
            headers.update(
                create_internal_auth_headers(
                    user, claims=claims.as_json_dict() if claims else None, impersonation=impersonation
                )
            )
        return kwargs

    def process_response(self, proxy, request, upstream_response, response):
        # user agents from browsers always have "mozilla" in the value, and we want to send that info only when it is relevant
        # i.e. when the SPA is talking to service router.
        if self._spa_version_info and "mozilla" in request.META.get("HTTP_USER_AGENT", "").lower():
            # Prevent the UI from triggering a reload as the service is starting, which presumably means that the deployment is still rolling out.
            prevent_reload = int(time.time() - process_start_time) < PREVENT_RELOAD_THRESHOLD_SEC
            if prevent_reload:
                spa_version = {"no_reload": True, **self._spa_version_info}
                spa_version_json = json.dumps(spa_version)
            else:
                spa_version_json = self._spa_version_info_json
            response["X-SPA-Version"] = spa_version_json
        return response
