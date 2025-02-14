# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from threading import local

_locals = local()


def get_current_request():
    return getattr(_locals, "django_request", None)


def save_current_request(request=None) -> None:
    _locals.django_request = request


def get_current_request_id() -> str | None:
    req = get_current_request()
    return getattr(req, "request_id", None) if req else None
