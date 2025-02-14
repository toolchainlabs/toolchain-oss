# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid
from pathlib import Path

from toolchain.django.site.settings.service import *  # noqa: F40
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

INSTALLED_APPS.extend(
    (
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.notifications.email.apps.EmailAppConfig",
    )
)
AUTH_USER_MODEL = "site.ToolchainUser"

# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"notifications-wf{uuid.uuid4()}☠️👾"

if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    RENDER_EMAIL_S3_BUCKET = config.get("RENDER_EMAIL_BUCKET", f"email-dev.{AWS_REGION}.toolchain.com")
    RENDER_EMAIL_S3_BASE_PATH = Path("dev") / NAMESPACE / "emails"

elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    RENDER_EMAIL_S3_BUCKET = config["RENDER_EMAIL_BUCKET"]
    RENDER_EMAIL_S3_BASE_PATH = Path("prod") / "v1" / "emails"


set_up_databases(__name__, "users", "notifications")
