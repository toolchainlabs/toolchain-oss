# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import textwrap

from csp.decorators import csp_exempt
from django.conf import settings
from django.http import HttpResponse
from django.urls import URLPattern, path
from django.views import View

_SECURITY_TXT = textwrap.dedent(
    """
    Contact: security@toolchain.com
    Expires: Tue, 14 Oct 2025 10:00 -0700
    Preferred-Languages: en
    Canonical: https://toolchain.com/.well-known/security.txt
    Canonical: https://app.toolchain.com/.well-known/security.txt
    """
)

_ROBOTS_TXT_ALLOW_INDEXING = "User-agent: *\nDisallow:"
_ROBOTS_TXT_DISALLOW_INDEXING = "User-agent: *\nDisallow: /"


@csp_exempt
def robots_txt_allow(request):
    return HttpResponse(content=_ROBOTS_TXT_ALLOW_INDEXING, content_type="text/plain")


@csp_exempt
def robots_txt_disallow(request):
    return HttpResponse(content=_ROBOTS_TXT_DISALLOW_INDEXING, content_type="text/plain")


@csp_exempt
def robots_txt_dynamic(request):
    content = _ROBOTS_TXT_ALLOW_INDEXING if settings.TOOLCHAIN_ENV.is_prod_namespace else _ROBOTS_TXT_DISALLOW_INDEXING
    return HttpResponse(content=content, content_type="text/plain")


robots_txt_allow.view_type = "app"
robots_txt_disallow.view_type = "app"
robots_txt_dynamic.view_type = "app"


class SecurityTxt(View):
    view_type = "app"

    def get(self, _):
        return HttpResponse(content=_SECURITY_TXT, content_type="text/plain")


def get_well_known_urls() -> list:
    # https://en.wikipedia.org/wiki/List_of_/.well-known/_services_offered_by_webservers
    return [
        path(".well-known/security.txt", SecurityTxt.as_view(), name="security-txt"),
    ]


def get_robots_txt_url(allow_indexing: bool) -> URLPattern:
    view_func = robots_txt_allow if allow_indexing else robots_txt_disallow
    return path("robots.txt", view_func, name="robots-txt")


def get_robots_txt_dynamic() -> URLPattern:
    return path("robots.txt", robots_txt_dynamic, name="robots-txt")
