# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import logging

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponseServerError, JsonResponse
from django.views import View
from rest_framework import status
from rest_framework.exceptions import APIException

_logger = logging.getLogger(__name__)


class BadApiRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid"

    def __init__(self, detail=None, code=None):
        _logger.warning(detail, exc_info=True)
        super().__init__(detail, code)


class ToolchainAccessMixin(AccessMixin):
    def handle_no_permission(self):
        # Based on django.contrib.auth.mixins.LoginRequiredMixin but w/ support for toolchain  internal auth / JwtMiddleware
        user = _get_request_user(self.request)
        _logger.warning(
            f"handle_no_permission - path={self.request.path} {user} raise_exception={self.raise_exception}"
        )
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        login_url = self.get_login_url()
        next_url = self.request.build_absolute_uri()
        _logger.info(f"redirect to login: {login_url=} {next_url=}")
        return redirect_to_login(next=next_url, login_url=login_url, redirect_field_name=self.get_redirect_field_name())


class ToolchainLoginRequiredMixin(ToolchainAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        user = _get_request_user(request)
        if not user.is_authenticated:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def _get_request_user(request):
    if hasattr(request, "toolchain_user"):  # JwtMiddleware
        user = request.toolchain_user
    elif hasattr(request, "internal_service_call_user"):  # InternalServicesMiddleware
        user = request.internal_service_call_user
    if user:
        return user
    # Temporary fix while we still have django auth around.
    # Should be removed once we get rid of django auth in favor of our internal middlewares (jwt/internal services) always setting request.user
    return getattr(request, "user", None) or AnonymousUser()


class AjaxView(View):
    returns_list = False

    class Error(Exception):
        pass

    class JsonEncoder(DjangoJSONEncoder):
        def default(self, o):
            # See "Date Time String Format" in the ECMA-262 specification.
            if isinstance(o, datetime.datetime):
                # Convert to ISO 8601 date format (parseable by JS's Date.parse()).
                return o.isoformat()
            return super().default(o)

    def get(self, request, *args, **kwargs):
        return self._process(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._process(request, *args, **kwargs)

    def _process(self, request, *args, **kwargs):
        try:
            data = self.get_ajax_data()
            return JsonResponse(data, encoder=self.JsonEncoder, safe=not self.returns_list)
        except self.Error as e:
            return HttpResponseServerError(content=str(e))

    def get_ajax_data(self):
        """Subclasses implement this to return a JSON-encodable data structure."""
        raise NotImplementedError()
