# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from typing import Mapping

from pants.option.global_options import AuthPluginResult, AuthPluginState
from pants.option.options import Options

from toolchain.base.datetime_tools import utcnow
from toolchain.pants.auth.rules import AuthStoreOptions
from toolchain.pants.auth.store import AuthStore
from toolchain.pants.common.toolchain_setup import ToolchainSetup

_PLUGIN_NAME = "Toolchain Remote Cache Auth Plugin"
_DISABLED_AUTH = AuthPluginResult(
    state=AuthPluginState.UNAVAILABLE,
    execution_headers={},
    store_headers={},
    instance_name=None,
    plugin_name="Toolchain Remote Cache Auth Plugin",
)

_logger = logging.getLogger(__name__)


def toolchain_auth_plugin(
    initial_execution_headers: dict[str, str],
    initial_store_headers: dict[str, str],
    options: Options,
    env: Mapping[str, str],
    prior_result: AuthPluginResult | None = None,
    **kwargs,
) -> AuthPluginResult:
    now = utcnow()
    if prior_result and prior_result.expiration and prior_result.is_available and now < prior_result.expiration:
        return prior_result
    store = _auth_store_from_options(options, env)
    if not store:
        return _DISABLED_AUTH
    access_token = store.get_access_token()
    config = store.get_remote_client_config()
    if not access_token.has_token:
        return _DISABLED_AUTH

    access_token_headers = access_token.get_headers()
    keys_for_access_token_headers = frozenset(access_token_headers.keys())

    overwritten_execution_header_keys = frozenset(initial_execution_headers.keys()).intersection(
        keys_for_access_token_headers
    )
    if overwritten_execution_header_keys:
        _logger.warning(
            f"The following remote execution header(s) will be overwritten by the Toolchain plugin: {', '.join(overwritten_execution_header_keys)}"
        )

    overwritten_store_header_keys = frozenset(initial_store_headers.keys()).intersection(keys_for_access_token_headers)
    if overwritten_store_header_keys:
        _logger.warning(
            f"The following remote store header(s) will be overwritten by the Toolchain plugin: {', '.join(overwritten_store_header_keys)}"
        )
    execution_address = config.exec_address if config else None
    return AuthPluginResult(
        state=AuthPluginState.OK,
        execution_headers={**initial_execution_headers, **access_token_headers},
        store_headers={**initial_store_headers, **access_token_headers},
        instance_name=access_token.customer_id,
        expiration=access_token.expires_at - store.token_expiration_threshold,
        store_address=config.cache_address if config else None,
        execution_address=execution_address,
        plugin_name=_PLUGIN_NAME,
    )


def _auth_store_from_options(options: Options, env: Mapping[str, str]) -> AuthStore | None:
    pants_bin_name = options.for_global_scope().pants_bin_name
    auth_options = options.for_scope(AuthStoreOptions.options_scope)
    setup_options = options.for_scope(ToolchainSetup.options_scope)
    repo_slug = setup_options.repo
    if not repo_slug:
        return None
    return AuthStore(
        context="auth-plugin",
        options=auth_options,
        pants_bin_name=pants_bin_name,
        env=env,
        repo=repo_slug,
        base_url=setup_options.base_url,
    )
