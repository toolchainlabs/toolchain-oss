# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.dependency.api.urls import urlpatterns
from toolchain.django.site.views.urls_api_base import api_urlpatterns_base

urlpatterns.extend(api_urlpatterns_base(with_schema=True))
