# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from toolchain.django.resources.template_loaders import get_jinja2_template_config
from toolchain.django.site.settings.util import get_middleware

LOGIN_URL = "/auth/login/"

TEMPLATES_CFG = get_jinja2_template_config(add_csp_extension=True)
SERVICE_ROUTER_MIDDLEWARE = get_middleware(
    auth_mode=None, auth_middleware=(("toolchain.users.jwt.middleware.JwtAuthMiddleware",)), with_csp=True
)

SECURE_HSTS_SECONDS = int(datetime.timedelta(days=180).total_seconds())
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
