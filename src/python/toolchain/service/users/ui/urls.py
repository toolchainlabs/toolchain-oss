# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.views.urls_base import urlpatterns_base
from toolchain.users.ui.urls import urlpatterns as users_urlpatterns

urlpatterns = urlpatterns_base() + users_urlpatterns
