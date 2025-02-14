# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Callable

from django.apps import apps
from django.conf import settings
from django.db import connections
from django.urls import URLPattern, include, path

from toolchain.django.db.db_router_registry import DBRouterRegistry
from toolchain.django.db.per_app_db_router import PerAppDBRouter
from toolchain.toolshed.admin_models.loader import AdminModelsMap
from toolchain.toolshed.postgres_db_views import get_views_urls
from toolchain.toolshed.site import RootLinks, ToolshedAdminSite
from toolchain.workflow.admin_views import get_workflow_admin_urls


def _get_admin_sites() -> Iterator[tuple[ToolshedAdminSite, str]]:
    routes = DBRouterRegistry.get_routers_by_db(settings.SERVICE_INFO.name)
    for db_name in connections.databases.keys():
        if db_name == "default":
            continue
        yield _get_site_for_database(db_name, routes[db_name]), db_name


def _get_site_for_database(db_name: str, db_router: PerAppDBRouter) -> ToolshedAdminSite:
    is_default = db_name == "users"
    site = ToolshedAdminSite.for_database(db_name=db_name, is_default=is_default)
    models_map = AdminModelsMap(is_dev=settings.TOOLCHAIN_ENV.is_dev)
    for app_label in db_router.app_labels_to_route:
        if app_label not in apps.app_configs:
            continue
        for model in apps.get_app_config(app_label).get_models():
            admin_cls = models_map.get_admin_class(model)
            if admin_cls is False:
                continue
            site.register(model, admin_class=admin_cls)
    return site


@dataclass(frozen=True)
class ExtensionUrls:
    url_path: str
    get_urls_func: Callable
    app_name: str
    namespace: str

    def to_path(self, db_name: str, prefix: str) -> URLPattern:
        urls = self.get_urls_func(db_name)
        return path(f"{prefix}/{self.url_path}", include((urls, self.app_name), namespace=self.namespace))


def get_urls() -> list[URLPattern]:
    admin_urls = []
    workflow_links = []
    admin_links = []
    db_state_links = []
    apps_for_db = DBRouterRegistry.get_apps_for_db(settings.SERVICE_INFO.name)
    for site, db_name in _get_admin_sites():
        db_stats_urls = get_views_urls(db_name)
        prefix = f"db/{db_name}"
        admin_urls.extend([path(f"{prefix}/admin/", site.urls), path(f"{prefix}/dbz/", include(db_stats_urls))])
        admin_links.append((site.human_db_name, f"{prefix}/admin/"))
        db_state_links.append((site.human_db_name, f"{prefix}/dbz/"))
        if "workflow" in apps_for_db[db_name]:
            workflow_links.append((site.human_db_name, _add_workflow_links(prefix, admin_urls, db_name)))
    root_links: RootLinks = {
        "workflow": workflow_links,
        "admin": admin_links,
        "db_state": db_state_links,
    }
    admin_urls.extend(ToolshedAdminSite.get_global_urls(root_links))
    return admin_urls


def _add_workflow_links(prefix: str, admin_urls: list[URLPattern], db_name: str) -> str:
    workflow_urls = get_workflow_admin_urls(db_name)
    base_path = f"{prefix}/workflow/"
    admin_urls.append(path(base_path, include((workflow_urls, "workflow_admin"), namespace=f"workflow-{db_name}")))
    return f"{base_path}summary/"
