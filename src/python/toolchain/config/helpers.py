# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.config.services import get_gunicorn_service
from toolchain.constants import ToolchainEnv
from toolchain.util.config.app_config import AppConfig


def get_login_url(toolchain_env: ToolchainEnv, config: AppConfig) -> str:
    if toolchain_env.is_dev:  # type: ignore[attr-defined]
        servicerouter_dev_port = get_gunicorn_service("servicerouter").dev_port
        return f"http://localhost:{servicerouter_dev_port}/auth/login/"
    _login_url_host = config.get("LOGIN_URL_HOST", "app.toolchain.com")
    return f"https://{_login_url_host}/auth/login/"
