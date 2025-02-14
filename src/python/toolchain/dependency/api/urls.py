# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path
from rest_framework_nested import routers

from toolchain.dependency.api import views
from toolchain.dependency.api.resolver_api import ResolveViewSet

router = routers.SimpleRouter()
router.register("packagerepo", views.PackageRepoViewSet, basename="packagerepo")

packagerepo_router = routers.NestedSimpleRouter(router, "packagerepo", lookup="packagerepo")
packagerepo_router.register("projects", views.ProjectsViewSet, basename="projects")
packagerepo_router.register("distributions", views.DistributionsViewSet, basename="distributions")
packagerepo_router.register("resolve", ResolveViewSet, basename="resolve")
packagerepo_router.register("modules", views.ModulesViewSet, basename="modules")

projects_router = routers.NestedSimpleRouter(packagerepo_router, "projects", lookup="project")
projects_router.register("releases", views.ReleasesViewSet, basename="releases")

releases_router = routers.NestedSimpleRouter(projects_router, "releases", lookup="release")
releases_router.register("artifacts", views.ArtifactsViewSet, basename="artifacts")

artifacts_router = routers.NestedSimpleRouter(releases_router, "artifacts", lookup="artifact")
artifacts_router.register("dependencies", views.DependenciesViewSet, basename="dependencies")

urlpatterns = [
    path(
        "v1/",
        include(
            router.urls + packagerepo_router.urls + projects_router.urls + releases_router.urls + artifacts_router.urls
        ),
    )
]
