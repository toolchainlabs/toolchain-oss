# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware

USERS_UI_URLS = "toolchain.users.ui.urls"
USERS_UI_MIDDLEWARE = get_middleware(
    auth_mode=MiddlewareAuthMode.INTERNAL,
    with_csp=True,
    append_middleware=(
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",  # Used for the accept TOS flow
        "toolchain.users.ui.middleware.ToolchainAuthExceptionMiddleware",
    ),
)

# See https://python-social-auth.readthedocs.io/en/latest/pipeline.html#authentication-pipeline.
USERS_SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "toolchain.users.ui.auth_util.check_is_user_allowed",
    "toolchain.users.ui.auth_util.load_user",
    "toolchain.users.ui.auth_util.create_user",
    "toolchain.users.ui.auth_util.update_user_details",
)
