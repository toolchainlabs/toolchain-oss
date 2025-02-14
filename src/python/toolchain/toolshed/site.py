# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.contrib.admin import AdminSite
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.urls import URLPattern, path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.toolshed.cookie import AuthCookie
from toolchain.toolshed.url_names import URLNames
from toolchain.toolshed.views import AdminLoginView, DuoAuthCallbackView, DuoAuthView, ToolshedIndexView

_logger = logging.getLogger(__name__)

RootLinks = dict[str, list[tuple[str, str]]]


class ToolshedAdminSite(AdminSite):
    _default_site = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tc_request = None

    @classmethod
    def for_database(cls, *, db_name: str, is_default: bool) -> ToolshedAdminSite:
        site = cls(f"{db_name}-admin")
        site.human_db_name = db_name.capitalize().replace("_", " ")
        site.index_title = f"DB Admin: {site.human_db_name}"
        site.site_header = "Toolshed admin service"
        if is_default:
            if cls._default_site:
                raise ToolchainAssertion(f"Default site already defined: {cls._default_site.index_title}")
            cls._default_site = site
        return site

    @classmethod
    def login_error(cls, request, error_message):
        return cls._default_site.login(request, extra_context={"error": error_message})

    def _get_duo_auth_view(self):
        def duo_auth_view(request):
            context = self.each_context(request)
            context["is_nav_sidebar_enabled"] = False
            request.current_app = self.name
            return DuoAuthView.as_view()(request)

        return duo_auth_view

    @classmethod
    def _get_default_site(cls) -> ToolshedAdminSite:
        site = cls._default_site
        if not site:
            raise ToolchainAssertion("Default site not initialized")
        return site

    @classmethod
    def get_global_urls(cls, root_links: RootLinks) -> tuple[URLPattern, ...]:
        site = cls._get_default_site()
        return (
            path("", site._get_full_index_view(root_links), name=URLNames.INDEX),
            path("auth/2fa/", site._get_duo_auth_view(), name=URLNames.DUO_AUTH),
            path("auth/callback/", DuoAuthCallbackView.as_view(), name=URLNames.DUO_CALLBACK),
            path("auth/login/", site.login, name=URLNames.LOGIN),
        )

    @classmethod
    def check_permissions_for_request(cls, request) -> bool:
        return cls._get_default_site().has_permission(request)

    @property
    def site_url(self) -> str:
        return reverse(URLNames.INDEX)

    def _get_full_index_view(self, root_links: RootLinks):
        def full_index_view(request):
            context = self.each_context(request)
            context["is_nav_sidebar_enabled"] = False
            context.update(links_data=root_links)
            request.current_app = self.name
            return ToolshedIndexView.as_view(extra_context=context)(request)

        return self.admin_view(full_index_view)

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        if self.has_permission(request):
            return HttpResponseRedirect(reverse(URLNames.INDEX))
        context = self.each_context(request)
        if REDIRECT_FIELD_NAME not in request.GET and REDIRECT_FIELD_NAME not in request.POST:
            context[REDIRECT_FIELD_NAME] = self.site_url
        context.update(extra_context or {})
        request.current_app = self.name
        return AdminLoginView.as_view(extra_context=context)(request)

    @method_decorator(never_cache)
    def logout(self, request, extra_context=None):
        response = super().logout(request, extra_context=extra_context)
        AuthCookie.clear_cookie(response)
        return response

    def each_context(self, request):
        self._tc_request = request
        ctx = super().each_context(request)
        self._tc_request = None
        return ctx

    @property
    def enable_nav_sidebar(self) -> bool:
        # _tc_request will be None when django runs admin site checks (admin/checks.py:check_dependencies)
        return self.has_permission(self._tc_request) if self._tc_request else False

    def has_permission(self, request) -> bool:
        valid_user = super().has_permission(request)
        if not valid_user:
            _logger.warning(f"user {request.user} is not valid.")
            return False
        user = request.user
        has_cookie = AuthCookie.exists(request, user.api_id)
        if not has_cookie:
            _logger.info(f"Missing 2FA cookie for {user}. cookies: {request.COOKIES.keys()}")
        return has_cookie
