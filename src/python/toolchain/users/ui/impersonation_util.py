# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied

from toolchain.django.site.models import ToolchainUser

_logger = logging.getLogger(__name__)


def user_can_be_impersonated(
    user: ToolchainUser, raise_http_forbidden: bool = False, impersonator_api_id: str | None = None
):
    """Checks whether user `user` is generally allowed to be impersonated.

    Usual behaviour is to return a boolean (true if the impersonation is valid, otherwise false), but if
    `raise_http_forbidden` is `True`, we raise an HTTP 403 error and log a warning if the impersonation we're checking
    is invalid. If `raise_http_forbidden` is true, then `impersonator_api_id` should be set, so that the log messages
    make sense)
    """

    if not user.is_active:
        if raise_http_forbidden:
            _warn_and_raise_403(
                f"User {impersonator_api_id} requested a session to impersonate another inactive user {user.api_id}. Giving a 403.",
                "You may not impersonate inactive users.",
            )

        return False

    if user.is_staff or user.is_superuser:
        if raise_http_forbidden:
            _warn_and_raise_403(
                f"User {impersonator_api_id} requested a session to impersonate staff member {user.api_id}. Giving a 403.",
                "You may not impersonate inactive users.",
            )

        return False

    return True


def _warn_and_raise_403(log_message: str, exception_message: str):
    _logger.warning(log_message)
    raise PermissionDenied(exception_message)
