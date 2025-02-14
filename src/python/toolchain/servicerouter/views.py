# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import datetime
import json
import logging
from typing import Any

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView, View

from toolchain.django.spa.config import StaticContentConfig
from toolchain.django.util.view_util import ToolchainLoginRequiredMixin
from toolchain.servicerouter.source_maps_helper import get_cloudfront_cookies

_logger = logging.getLogger(__name__)


def missing_api_view(request):
    _logger.warning(f"No API mounted at {request.path}")
    raise Http404


def _get_assets_json(static_asset_cfg: StaticContentConfig) -> dict | None:
    if static_asset_cfg.is_local:
        return None
    return {"version": static_asset_cfg.version, "timestamp": static_asset_cfg.timestamp, "disableVersionCheck": False}


class FrontendApp(ToolchainLoginRequiredMixin, TemplateView):
    view_type = "app"
    template_name = "servicerouter/index.html"
    _SRC_MAP_COOKIE_TTL = datetime.timedelta(days=10)

    def __init__(self) -> None:
        super().__init__()
        self._static_asset_cfg: StaticContentConfig = settings.STATIC_CONTENT_CONFIG
        scripts_base = staticfiles_storage.url("servicerouter/generated/")
        self._js_bundles = [f"{scripts_base}{bundle}" for bundle in self._static_asset_cfg.bundles]

    def _get_client_init_data(self, request) -> dict[str, Any]:
        user = request.user
        show_sentry_test_button = request.GET.get("sentry_check") == "1" and user.is_staff
        data: dict[str, Any] = {
            "host": f"{request.scheme}://{request.get_host()}",
            "support_link": "https://github.com/toolchainlabs/issues/issues",
        }
        impersonation = getattr(request, "toolchain_impersonation", None)
        if impersonation:
            data["impersonation"] = impersonation.to_json_dict()
        if settings.JS_SENTRY_DSN:
            tc_env = settings.TOOLCHAIN_ENV
            # Note: the sentry dict/obj is passed as is by the UI to the sentry JS sdk init function.
            # https://docs.sentry.io/platforms/javascript/guides/react/configuration/options/
            # See: src/utils/init-data.ts
            sentry_data = {
                "dsn": settings.JS_SENTRY_DSN,
                "environment": tc_env.namespace or tc_env.get_env_name(),
                "release": self._static_asset_cfg.version,
                "initialScope": {
                    "user": {
                        "id": user.api_id,
                        "email": user.email,
                        "username": user.username,
                    },
                },
            }
            if impersonation:
                sentry_data["initialScope"]["impersonation"] = impersonation.to_json_dict()
            data["sentry"] = sentry_data
            if show_sentry_test_button:
                data["flags"] = {"error_check": True}

        assets_json = _get_assets_json(self._static_asset_cfg)
        if assets_json:
            assets_json["base_path"] = staticfiles_storage.url("servicerouter/generated/")
            data["assets"] = assets_json
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = self._get_client_init_data(self.request)
        # We base64 encode to prevent XSS if we at some point in the future user supplied data makes it into this dict.
        init_data = base64.b64encode(json.dumps(data).encode())
        # We mark_safe here otherwise, django will escape this string, which will break it.
        favicon_path = "servicerouter/images/" if self._static_asset_cfg.is_local else ""
        scripts_base = staticfiles_storage.url("servicerouter/generated/")

        context.update(
            js_bundles=self._js_bundles,
            init_data=mark_safe(init_data.decode()),  # nosec: B703, B308
            scripts_base=scripts_base,
            # for now, we need to server it from CDN/S3 eventually
            favicon=staticfiles_storage.url(f"{favicon_path}favicon.png"),
        )
        return context

    def render_to_response(self, context, **response_kwargs) -> HttpResponse:
        response = super().render_to_response(context, **response_kwargs)
        static_asset_cfg: StaticContentConfig = settings.STATIC_CONTENT_CONFIG
        if not self.request.user.is_staff:
            return response

        cookies, assets_domain = get_cloudfront_cookies(static_asset_cfg, policy_ttl=self._SRC_MAP_COOKIE_TTL)
        for name, value in cookies.items():
            response.set_cookie(key=name, value=value, domain=assets_domain, httponly=True, secure=True)
        return response

    def get(self, request, *args, **kwargs):
        user = request.user
        if not user.is_associated_with_active_customers():
            _logger.info(f"user {user} - not associated with any active customer, redirect to new org onboarding flow")
            return HttpResponseRedirect(redirect_to="/org/")
        return super().get(request, *args, **kwargs)


class AssetsVersionsView(View):
    def get(self, _):
        assets_json = _get_assets_json(settings.STATIC_CONTENT_CONFIG) or {"version": "local"}
        return JsonResponse(assets_json)
