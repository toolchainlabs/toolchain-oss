# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.utils.deprecation import MiddlewareMixin

from toolchain.django.auth.utils import get_auth_data, is_internal_call
from toolchain.django.site.models import ToolchainUser

_logger = logging.getLogger(__name__)


class InternalServicesMiddleware(MiddlewareMixin):
    def process_request(self, request) -> None:
        if request.view_type != "app":  # from ToolchainRequestMiddleware
            request.is_toolchain_internal_call = False
            request.user = ToolchainUser.get_anonymous_user()
            return
        request.is_toolchain_internal_call = is_internal_call(request.headers)
        auth_data = get_auth_data(request.headers, path=request.path)
        if not auth_data:
            # Not sure if this is legit use case. logging to see if we hit it.
            _logger.warning(f"internal_service_middleware no_auth_data {request.path=} {request.method=}")
            request.internal_service_call_user = None
            request.toolchain_claims = None
            request.toolchain_impersonation = None
            request.user = ToolchainUser.get_anonymous_user()
            return
        request.internal_service_call_user = auth_data.user
        request.toolchain_claims = auth_data.claims
        request.toolchain_impersonation = auth_data.impersonation
        request.user = auth_data.user
        request.customer_id = getattr(auth_data.claims, "customer_pk", "unkown")
