# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path
from rest_framework.schemas import get_schema_view

from toolchain.django.site.views.urls_base import urlpatterns_base


def api_urlpatterns_base(dependent_resources_check_view=None, with_schema=False):
    urls = urlpatterns_base(dependent_resources_check_view=dependent_resources_check_view)
    if with_schema:
        urls.append(path("schema", get_schema_view()))
    return urls
