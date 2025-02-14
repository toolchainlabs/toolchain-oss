# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.views.urls_api_base import api_urlpatterns_base
from toolchain.users.dependent_resources_check import DependentResourcesCheckz
from toolchain.users.urls_api import urlpatterns

urlpatterns.extend(
    api_urlpatterns_base(dependent_resources_check_view=DependentResourcesCheckz.as_view(), with_schema=True)
)
