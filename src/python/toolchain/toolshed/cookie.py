# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from toolchain.toolshed.config import AuthCookieConfig


class AuthCookie:
    @classmethod
    def _get_cfg(cls) -> AuthCookieConfig:
        return settings.AUTH_COOKIE_CONFIG

    @classmethod
    def store_cookie(cls, response: HttpResponse, user_api_id: str) -> None:
        cfg = cls._get_cfg()
        response.set_signed_cookie(
            key=cfg.name,
            value=user_api_id,
            salt=cfg.salt,
            max_age=cfg.max_age_sec,
            domain=cfg.domain,
            secure=cfg.is_secure,
            httponly=True,
            samesite="Lax",
        )

    @classmethod
    def load_cookie(cls, request: HttpRequest) -> str | None:
        # TODO: handle exceptions
        # Check that cookie matches user
        cfg = cls._get_cfg()
        return request.get_signed_cookie(key=cfg.name, default=None, salt=cfg.salt, max_age=cfg.max_age_sec)

    @classmethod
    def exists(cls, request: HttpRequest, user_api_id: str) -> bool:
        return cls.load_cookie(request) == user_api_id

    @classmethod
    def clear_cookie(cls, response: HttpResponse) -> None:
        cfg = cls._get_cfg()
        response.delete_cookie(key=cfg.name, domain=cfg.domain)
