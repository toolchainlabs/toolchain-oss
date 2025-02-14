# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from rest_framework.authentication import BaseAuthentication

from toolchain.django.auth.utils import INTERNAL_AUTH_HEADER

_logger = logging.getLogger(__name__)


class InternalViewAuthentication(BaseAuthentication):
    def authenticate(self, request):
        user = request.internal_service_call_user
        return (user, None) if user else None

    def authenticate_header(self, request):
        return f"Missing/invalid {INTERNAL_AUTH_HEADER}"
