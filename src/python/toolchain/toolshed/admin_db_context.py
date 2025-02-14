# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.django.db.db_router_registry import DBRouterRegistry
from toolchain.django.site.middleware.request_context import get_current_request


def set_db_context(db_name: str | None, request=None) -> None:
    if request:  # when calling this from shell, this will be None
        request._toolchain_db_admin_context = db_name
    DBRouterRegistry.set_default_db_name(db_name)


def get_db_context() -> str | None:
    request = get_current_request()
    if not request:
        return DBRouterRegistry.get_default_db_name()
    return getattr(request, "_toolchain_db_admin_context", None)
