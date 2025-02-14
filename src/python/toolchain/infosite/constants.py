# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware

EXTERNAL_RESOURCES: dict[str, tuple[str, ...]] = {
    "styles": (
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
    ),
    "scripts": ("cdnjs.cloudflare.com", "www.googletagmanager.com"),
    "fonts": ("fonts.gstatic.com",),
}

INFOSITE_APPS = ["django.contrib.staticfiles", "django_prometheus", "toolchain.infosite.apps.InfositeAppConfig"]

INFOSITE_MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=True)
