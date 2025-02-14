# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterable
from functools import cached_property

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.buildsense_db_router import BuildSenseDBRouter
from toolchain.django.db.dependency_db_router import DependencyDBRouter
from toolchain.django.db.maven_db_router import MavenDBRouter
from toolchain.django.db.notifications_db_router import NotificationsDBRouter
from toolchain.django.db.oss_metrics_db_router import OssMetricsDBRouter
from toolchain.django.db.pants_demos_db_router import PantsDemosDBRouter
from toolchain.django.db.payments_db_router import PaymentsDBRouter
from toolchain.django.db.per_app_db_router import PerAppDBRouter
from toolchain.django.db.pypi_db_router import PyPiDBRouter
from toolchain.django.db.scm_integration_db_router import ScmIntegrationBRouter
from toolchain.django.db.users_db_router import UsersDBRouter

DBRouters = tuple[PerAppDBRouter, ...]


class DBRouterRegistry:
    _known_routers = (
        BuildSenseDBRouter,
        MavenDBRouter,
        PyPiDBRouter,
        UsersDBRouter,
        DependencyDBRouter,
        ScmIntegrationBRouter,
        PantsDemosDBRouter,
        OssMetricsDBRouter,
        PaymentsDBRouter,
        NotificationsDBRouter,
    )
    _instance = None
    _default_db_name: str | None = None

    def validate_routers(self, routers: Iterable[PerAppDBRouter]):
        """Ensure that the specified routers are mutually compatible."""
        app_labels_seen = set()
        for router in routers:
            # Check that each app is routed by just one router.
            for app_label in router.app_labels_to_route:
                if app_label in app_labels_seen:
                    dbs_str = ", ".join(route.db_to_route_to for route in routers)
                    raise ToolchainAssertion(
                        f"App {app_label} is routed by more than one router among those for the dbs: {dbs_str}"
                    )
                app_labels_seen.add(app_label)

    @classmethod
    def set_default_db_name(cls, db_name: str | None = None):
        cls._default_db_name = db_name

    @classmethod
    def get_default_db_name(cls) -> str | None:
        return cls._default_db_name

    @classmethod
    def get_routers(cls, service_name: str, db_names: tuple[str, ...]) -> DBRouters:
        if cls._instance is not None:
            raise ToolchainAssertion("DBRouterRegistry.get_routers() should only be called once.")
        cls._instance = cls(service_name)
        return cls._instance._get_routes(db_names)

    @classmethod
    def get_db_name_for_app(cls, app_label: str) -> str:
        if cls._default_db_name:
            return cls._default_db_name
        registry = cls._instance
        if registry is None:
            return "default"
        return registry.db_for_app(app_label)

    @classmethod
    def get_routers_by_db(cls, service_name: str) -> dict[str, PerAppDBRouter]:
        """Return a map from db name to router instances that routes to that db."""
        ret: dict[str, PerAppDBRouter] = {}
        for router in cls.get_known_routers(service_name):
            db = router.db_to_route_to
            if db in ret:
                raise ToolchainAssertion(f"More than one router routing to database {db}")
            ret[db] = router
        return ret

    @classmethod
    def get_known_routers(cls, service_name: str) -> DBRouters:
        return tuple(rt(service_name) for rt in cls._known_routers)  # type: ignore

    def __init__(self, service_name: str):
        self._service_name = service_name
        self._db_to_routers: dict[str, PerAppDBRouter] = {}

    def _get_routes(self, db_names: tuple[str, ...]) -> DBRouters:
        routes_by_db = self.get_routers_by_db(self._service_name)
        self._db_to_routers = {db_name: routes_by_db[db_name] for db_name in db_names}
        # Ensure that the dbs are mutually compatible (i.e., the apps each one routes are mutually exclusive).
        routers = tuple(self._db_to_routers.values())
        self.validate_routers(routers)
        return routers

    @classmethod
    def get_apps_for_db(cls, service_name: str) -> dict[str, list[str]]:
        routers = cls.get_known_routers(service_name)
        return {router.db_to_route_to: sorted(router.app_labels_to_route) for router in routers}

    def db_for_app(self, app_label: str) -> str:
        """Return the name of the db to which the given app is routed."""
        try:
            return self._db_by_app[app_label]
        except KeyError:
            raise ToolchainAssertion(f"No known database routing for app {app_label}")

    @cached_property
    def _db_by_app(self):
        """Return a map from app label to name of db to which the app is routed."""
        ret = {}
        for router in self._db_to_routers.values():
            db = router.db_to_route_to
            for app_label in router.app_labels_to_route:
                ret[app_label] = db
        return ret
