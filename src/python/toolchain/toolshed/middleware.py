# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import re
from urllib.parse import urlencode

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from toolchain.toolshed.admin_db_context import set_db_context
from toolchain.toolshed.site import ToolshedAdminSite
from toolchain.toolshed.url_names import URLNames

_logger = logging.getLogger(__name__)


class AdminDbContextMiddleware(MiddlewareMixin):
    _DB_ADMIN_PATH = re.compile(r"^/db/(?P<db_name>\w+)/")

    def process_request(self, request):
        match = self._DB_ADMIN_PATH.match(request.path)
        if not match:
            return
        set_db_context(db_name=match.group("db_name"), request=request)

        def process_response(self, request, response):
            set_db_context(db_name=None, request=request)


class AuthMiddleware(MiddlewareMixin):
    _EXCLUDES = [re.compile("^/healthz"), re.compile("^/metricsz"), re.compile("^/auth/"), re.compile("^/checksz/")]

    def process_request(self, request):
        for exclude in self._EXCLUDES:
            if exclude.match(request.path):
                return None
        has_permissions = ToolshedAdminSite.check_permissions_for_request(request)
        if has_permissions:
            return None
        query_string = urlencode({REDIRECT_FIELD_NAME: request.path})
        path = reverse(URLNames.DUO_AUTH)
        _logger.warning(f"Missing cookies, redirect user from {request.path} to {path}")
        return HttpResponseRedirect(f"{path}?{query_string}")
