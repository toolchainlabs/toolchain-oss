# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path

from toolchain.django.site.views.urls_base import urlpatterns_base
from toolchain.toolshed.admin_site_generator import get_urls
from toolchain.toolshed.url_names import URLNames
from toolchain.toolshed.views import github_auth, github_complete, request_ui_impersonation

urlpatterns = (
    urlpatterns_base()
    + get_urls()
    + [
        path("auth/begin/", github_auth, name=URLNames.GITHUB_AUTH_BEGIN),
        path("auth/complete/", github_complete, name=URLNames.GITHUB_AUTH_COMPLETE),
        path(
            "impersonate/request/<str:user_api_id>/", request_ui_impersonation, name=URLNames.REQUEST_UI_IMPERSONATION
        ),
    ]
)
