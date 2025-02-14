# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse

from toolchain.django.auth.constants import REFRESH_TOKEN_COOKIE_NAME
from toolchain.django.site.models import ToolchainUser
from toolchain.users.jwt.utils import get_or_create_refresh_token_for_ui


def add_refresh_token_cookie(
    *, response: HttpResponse, user: ToolchainUser, impersonation_session: str | None = None
) -> None:
    token_str, expires_at = get_or_create_refresh_token_for_ui(user, impersonation_session)
    is_prod = settings.TOOLCHAIN_ENV.is_prod
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        value=token_str,
        expires=expires_at,
        secure=is_prod,
        httponly=False,
        samesite="Lax",
    )
