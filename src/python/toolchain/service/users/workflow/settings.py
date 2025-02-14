# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.users.constants import USERS_DB_DJANGO_APPS
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

INSTALLED_APPS.extend(USERS_DB_DJANGO_APPS)
CUSTOMER_EXPORT_S3_URL = config["CUSTOMER_EXPORT_S3_URL"]
REMOTE_WORKERS_TOKENS_EXPORT_S3_URL = config["REMOTE_WORKERS_TOKENS_EXPORT_S3_URL"]


TARGET_EMAIL_ADDRESS = "ops-notify@toolchain.com" if TOOLCHAIN_ENV.is_prod else f"{NAMESPACE}@toolchain.com"  # type: ignore[attr-defined]
set_up_databases(__name__, "users")
