# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path, re_path

from toolchain.django.site.views.urls_base import urlpatterns_base
from toolchain.django.site.views.well_known import get_robots_txt_url, get_well_known_urls
from toolchain.servicerouter.services_router import get_routing_urls
from toolchain.servicerouter.views import AssetsVersionsView, FrontendApp, missing_api_view

service_routes = get_routing_urls()

# Service routes come first as urlpatterns are matched in order and
# we want to have the frontend app catch requests to any other paths.
urlpatterns = (
    urlpatterns_base()
    + get_well_known_urls()
    + service_routes
    + [
        get_robots_txt_url(allow_indexing=False),
        path("checksz/versionsz", AssetsVersionsView.as_view(), name="versionz"),
        re_path(r"^api/", missing_api_view, name="missing-view"),
        re_path(r"^.*$", FrontendApp.as_view()),
    ]
)
