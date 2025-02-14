# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.db_router_registry import DBRouterRegistry
from toolchain.django.db.maven_db_router import MavenDBRouter
from toolchain.django.db.pypi_db_router import PyPiDBRouter
from toolchain.django.db.users_db_router import UsersDBRouter


def test_validate_routers():
    DBRouterRegistry("users").validate_routers(set())
    DBRouterRegistry("crawler/maven").validate_routers({MavenDBRouter("crawler/maven")})
    DBRouterRegistry("crawler/pypi").validate_routers({PyPiDBRouter("crawler/pypi")})
    DBRouterRegistry("crawler/pypi").validate_routers({PyPiDBRouter("crawler/pypi"), UsersDBRouter("crawler/pypi")})
    DBRouterRegistry("crawler/maven").validate_routers({MavenDBRouter("crawler/maven"), UsersDBRouter("crawler/maven")})

    # These are invalid together because they both route the workflow app.
    with pytest.raises(ToolchainAssertion, match="is routed by more than one router among those for the dbs:"):
        DBRouterRegistry("crawler/pypi").validate_routers({MavenDBRouter("crawler/pypi"), PyPiDBRouter("crawler/pypi")})

    with pytest.raises(ToolchainAssertion, match="is routed by more than one router among those for the dbs:"):
        DBRouterRegistry("crawler/maven").validate_routers(
            {MavenDBRouter("crawler/maven"), PyPiDBRouter("crawler/maven"), UsersDBRouter("crawler/maven")}
        )


def test_get_apps_for_db():
    assert DBRouterRegistry.get_apps_for_db("toolshed") == {
        "buildsense": ["buildsense", "ingestion", "workflow"],
        "maven": ["crawlerbase", "crawlermaven", "packagerepomaven", "webresource", "workflow"],
        "pypi": ["crawlerbase", "crawlerpypi", "packagerepopypi", "webresource", "workflow"],
        "users": ["admin", "auth", "sessions", "site", "users", "workflow"],
        "dependency": ["dependency", "workflow"],
        "scm_integration": ["bitbucket_integration", "github_integration", "workflow"],
        "pants_demos": ["pants_demos_depgraph", "workflow"],
        "oss_metrics": ["bugout_integration", "oss_metrics", "workflow"],
        "payments": ["amberflo_integration", "stripe_integration", "workflow"],
        "notifications": ["email_notifications", "workflow"],
    }


@pytest.mark.parametrize("service_name", ["users/ui", "users/api"])
def test_users_routes(service_name):
    routers = DBRouterRegistry.get_routers(service_name, ("users",))
    assert len(routers) == 1
    assert routers[0].db_to_route_to == "users"
    assert routers[0].app_labels_to_route == {"users", "admin", "auth", "sessions", "site", "workflow"}
    DBRouterRegistry._instance = None


@pytest.mark.parametrize("service_name", ["buildsense/api", "buildsense/worker"])
def test_buildsense_routes(service_name):
    routers = DBRouterRegistry.get_routers(service_name, ("users", "buildsense"))
    assert len(routers) == 2
    assert routers[1].db_to_route_to == "buildsense"
    assert routers[1].app_labels_to_route == {"workflow", "buildsense", "ingestion"}
    assert routers[0].db_to_route_to == "users"
    assert routers[0].app_labels_to_route == {"sessions", "site"}
    DBRouterRegistry._instance = None


@pytest.mark.parametrize("service_name", ["crawler/pypi/worker", "crawler/pypi/maintenance"])
def test_pypi_crawler_routes(service_name):
    routers = DBRouterRegistry.get_routers(service_name, ("pypi",))
    assert len(routers) == 1
    assert routers[0].db_to_route_to == "pypi"
    assert routers[0].app_labels_to_route == {
        "webresource",
        "workflow",
        "crawlerbase",
        "packagerepopypi",
        "crawlerpypi",
    }
    DBRouterRegistry._instance = None


def test_dependency_routes():
    routers = DBRouterRegistry.get_routers("dependency/api", ("pypi", "dependency"))
    assert len(routers) == 2
    assert routers[0].db_to_route_to == "pypi"
    assert routers[0].app_labels_to_route == {"webresource", "packagerepopypi"}
    assert routers[1].db_to_route_to == "dependency"
    assert routers[1].app_labels_to_route == {"dependency", "workflow"}
    DBRouterRegistry._instance = None
