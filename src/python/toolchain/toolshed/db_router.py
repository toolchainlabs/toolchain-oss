# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.django.db.db_router_registry import DBRouterRegistry
from toolchain.toolshed.admin_db_context import get_db_context


class RequestContextDBRouter:
    _DEFAULT_DB = "users"

    def __init__(self, service_name: str) -> None:
        self._routes = DBRouterRegistry.get_routers_by_db(service_name)

    @property
    def _router(self):
        db_name = get_db_context() or self._DEFAULT_DB
        return self._routes[db_name]

    def db_for_read(self, model, **hints):
        return self._router.db_for_read(model, **hints)

    def db_for_write(self, model, **hints):
        return self._router.db_for_write(model, **hints)

    def allow_relation(self, obj1, obj2, **hints) -> bool | None:
        for router in self._routes.values():
            allow = router.allow_relation(obj1, obj2)
            if allow is not None:
                return allow
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints) -> bool | None:
        db_name = self._DEFAULT_DB if db == "default" else db
        return self._routes[db_name].allow_migrate(db_name, app_label, model_name=model_name, **hints)
