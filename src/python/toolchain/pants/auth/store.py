# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from typing import Mapping

from pants.option.option_value_container import OptionValueContainer

from toolchain.base.datetime_tools import utcnow
from toolchain.pants.auth.client import AuthClient, AuthError, AuthState, RemoteClientConfig
from toolchain.pants.auth.subsystems import AuthStoreOptions
from toolchain.pants.auth.token import AuthToken

_logger = logging.getLogger(__name__)


class AuthStore:
    def __init__(
        self,
        context: str,
        options: OptionValueContainer | AuthStoreOptions,
        pants_bin_name: str,
        env: Mapping[str, str],
        repo: str | None,
        base_url: str,
    ) -> None:
        repo_slug = f"{options.org}/{repo}" if options.org and repo else None
        self._access_token: AuthToken | None = None
        self._remote_client_cfg: RemoteClientConfig | None = None
        self._state = AuthState.UNKNOWN
        self._env = env
        self.token_expiration_threshold = datetime.timedelta(minutes=options.token_expiration_threshold)
        self._client = AuthClient.create(
            context=context,
            pants_bin_name=pants_bin_name,
            base_url=f"{base_url}/api/v1",
            auth_file=options.auth_file,
            env_var=options.from_env_var,
            ci_env_vars=tuple(options.ci_env_variables),
            repo_slug=repo_slug,
            restricted_token_matches=options.restricted_token_matches,
        )

    @staticmethod
    def relevant_env_vars(options: OptionValueContainer | AuthStoreOptions) -> tuple[str, ...]:
        env_vars = set(options.ci_env_variables)
        if options.from_env_var:
            env_vars.add(options.from_env_var)
        return tuple(env_vars)

    def _get_access_token(self) -> AuthToken | None:
        access_token = self._access_token
        if access_token and not access_token.has_expired():
            return access_token
        try:
            token_and_cfg = self._client.acquire_access_token(self._env)
        except AuthError as error:
            _logger.log(level=error.log_level, msg=error.get_error_message())
            self._state = error.get_state()
        else:
            self._access_token = token_and_cfg.auth_token
            self._remote_client_cfg = token_and_cfg.remote_client_cfg
            self._state = AuthState.OK

        return self._access_token

    def load_refresh_token(self) -> AuthToken | None:
        return self._client.load_refresh_token(self._env)

    def get_token_info(self, verbose: bool, use_json: bool) -> tuple[str, ...]:
        auth_token = self.load_refresh_token()
        if not auth_token:
            return ("Token not found",)
        days_to_exiration = (auth_token.expires_at.date() - utcnow().date()).days
        token_info = [
            f"token id: {auth_token.token_id} expires at: {auth_token.expires_at} (in {days_to_exiration} days)."
        ]
        if verbose or use_json:
            if use_json:
                # We only want to output json data in this case, so it can be parsed by other tools, so we remove the default token info line.
                token_info = [json.dumps(auth_token.claims)]
            else:
                token_info.extend(f"{k}={v}" for k, v in sorted(auth_token.claims.items()))
        return tuple(token_info)

    def get_remote_client_config(self) -> RemoteClientConfig | None:
        return self._remote_client_cfg

    def get_access_token(self) -> AuthToken:
        return self._get_access_token() or AuthToken.no_token()

    def get_auth_state(self) -> AuthState:
        if self._state.is_final:
            return self._state
        self._get_access_token()
        return self._state
