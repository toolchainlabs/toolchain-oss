# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

USERS_API_URLS = "toolchain.users.urls_api"
USERS_DB_DJANGO_APPS = (
    "django.contrib.auth",
    "toolchain.django.site",
    "toolchain.users.apps.UsersAppConfig",
)
SUPPORT_EMAIL_ADDR = "support@toolchain.com"
CONTACT_TOOLCHAIN_MESSAGE = f"Please contact Toolchain at {SUPPORT_EMAIL_ADDR}"

CURRENT_TOS_VERSION = "toolchain-2022"
