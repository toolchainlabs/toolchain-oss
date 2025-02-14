# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.contrib.sitemaps.views import sitemap
from django.urls import URLPattern, path, re_path

from toolchain.pants_demos.depgraph.sitemap import DemoReposSitemap
from toolchain.pants_demos.depgraph.url_names import URLNames
from toolchain.pants_demos.depgraph.views import (
    REPO_FN_PART,
    ErrorPageAppView,
    PageNotFoundAppView,
    RepoApiView,
    RepoAppView,
    RepoSelectionApiView,
    RepoSelectionAppView,
    TOSPageAppView,
)


def get_app_urls() -> list[URLPattern]:
    return [
        path("api/v1/repos/", RepoSelectionApiView.as_view(), name=URLNames.REPO_SELECTION),
        re_path("api/v1/repos/" + REPO_FN_PART + "/", RepoApiView.as_view()),
        re_path("app/repo/" + REPO_FN_PART, RepoAppView.as_view(), name=URLNames.REPO_VIEW),
        path("", RepoSelectionAppView.as_view()),
        path("404", PageNotFoundAppView.as_view()),
        path("error", ErrorPageAppView.as_view()),
        path("terms", TOSPageAppView.as_view(), name=URLNames.TERMS),
        path(
            "sitemap.xml",
            sitemap,
            {"sitemaps": {"repos": DemoReposSitemap}},
            name="django.contrib.sitemaps.views.sitemap",
        ),
    ]
