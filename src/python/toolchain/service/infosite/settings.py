# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from django.utils.crypto import get_random_string

from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.settings.base import *  # noqa: F401, F403
from toolchain.infosite.constants import EXTERNAL_RESOURCES, INFOSITE_APPS, INFOSITE_MIDDLEWARE

ROOT_URLCONF = "toolchain.infosite.urls"

# Override the standard MIDDLEWARE and INSTALLED_APPS to remove any that require a database.

MIDDLEWARE = INFOSITE_MIDDLEWARE

INSTALLED_APPS = INFOSITE_APPS

TEMPLATES = get_jinja2_template_config(add_csp_extension=True)

CSP_FRAME_ANCESTORS = ("'none'",)
CSP_DEFAULT_SRC = ("'self'",)
CSP_FONT_SRC = EXTERNAL_RESOURCES["fonts"]
CSP_STYLE_SRC = ("'self'",) + EXTERNAL_RESOURCES["styles"]
CSP_SCRIPT_SRC = ("'self'",) + EXTERNAL_RESOURCES["scripts"]
CSP_CONNECT_SRC = ("'self'", "www.google-analytics.com")

CSP_INCLUDE_NONCE_IN = ("script-src",)

CSP_REPORT_ONLY = False
CSP_REPORT_URI = "https://toolchain.report-uri.com/r/d/csp/enforce"
SECRET_KEY = get_random_string(32)  # not important for infosite, but django wants it.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(datetime.timedelta(days=180).total_seconds())
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "origin"  # Allow sending the Referer header when redirecting to the toolchain app.

if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    # This header only works properly over https and we don't use https in dev.
    # https://docs.djangoproject.com/en/4.0/ref/middleware/#cross-origin-opener-policy
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None
