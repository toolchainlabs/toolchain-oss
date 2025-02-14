# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import uuid

from django.conf import settings
from django.urls import Resolver404, resolve
from django.utils.deprecation import MiddlewareMixin

from toolchain.django.site.middleware.request_context import save_current_request
from toolchain.util.constants import REQUEST_ID_HEADER
from toolchain.util.sentry.sentry_integration import set_context


class ToolchainRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        save_current_request(request)
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.request_id = request_id
        set_context(request_id=request_id, service=settings.SERVICE_INFO.name)
        request.view_type = _get_view_type(request.path)

    def process_response(self, request, response):
        response[REQUEST_ID_HEADER] = request.request_id
        return response


def _get_view_type(request_path: str) -> str | None:
    try:
        match = resolve(request_path)
    except Resolver404:
        return None
    view_func = match.func
    if hasattr(view_func, "view_type"):
        return view_func.view_type
    if hasattr(view_func, "cls"):
        view_cls = view_func.cls
    elif hasattr(view_func, "view_class"):
        view_cls = view_func.view_class
    else:
        return None
    return getattr(view_cls, "view_type", None)
