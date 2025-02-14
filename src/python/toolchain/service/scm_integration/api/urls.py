# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path

from toolchain.bitbucket_integration.api.urls import bitbucket_url_patterns
from toolchain.django.site.views.urls_api_base import api_urlpatterns_base
from toolchain.github_integration.api.resources_check import ResourcesCheckz
from toolchain.github_integration.api.urls import github_url_patterns

urlpatterns = [
    path("api/v1/github/", include(github_url_patterns)),
    path("api/v1/bitbucket/", include(bitbucket_url_patterns)),
] + api_urlpatterns_base(dependent_resources_check_view=ResourcesCheckz.as_view())
