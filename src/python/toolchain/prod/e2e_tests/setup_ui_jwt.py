#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.users.jwt.encoder import JWTEncoder
from toolchain.users.jwt.keys import JWTSecretData
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.secret.secrets_accessor import KubernetesSecretsAccessor, KubernetesVolumeSecretsReader

_logger = logging.getLogger(__name__)


class SetupUIJwt(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"SetupJwtAccessKey arguments: {cmd_args}")
        self._user_api_id = cmd_args.user_api_id
        self._username = cmd_args.username
        self._ttl = datetime.timedelta(minutes=cmd_args.ttl)
        if cmd_args.local:
            self._secrets = KubernetesSecretsAccessor.create_rotatable(
                get_remote_username(), cluster=KubernetesCluster.DEV
            )
        else:
            self._secrets = KubernetesVolumeSecretsReader.create_rotatable(base_path=cmd_args.secret_path)
        self._path = Path(cmd_args.path or "/access_tokens/token.jwt")

    def generate_jwt(self, encoder: JWTEncoder) -> None:
        now = utcnow()
        expires_at = now + self._ttl
        token_str = encoder.encode_refresh_token(  # nosec: B106
            token_id="ui-test",
            expires_at=expires_at,
            issued_at=now,
            audience=AccessTokenAudience.FRONTEND_API,
            username=self._username,
            user_api_id=self._user_api_id,
            bypass_db_check=True,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _logger.info(f"Saving UI JWT refresh token to {self._path.as_posix()} (username={self._username})")
        self._path.write_text(token_str)

    def run(self) -> int:
        secret_data = JWTSecretData.read_settings(toolchain_env=ToolchainEnv.PROD, secrets_reader=self._secrets)  # type: ignore[attr-defined]
        if not secret_data:
            raise ToolchainAssertion("Couldn't load JWT secrets via JWTSecretData.read_settings")
        encoder = JWTEncoder(secret_data, allow_bypass_db_claim=True)
        self.generate_jwt(encoder)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--user-api-id", action="store", required=True, help="user api id")
        parser.add_argument("--username", action="store", required=True, help="username")
        parser.add_argument("--path", action="store", required=True, help="full path to save token")
        parser.add_argument("--secret-path", action="store", required=False, help="secret path")
        parser.add_argument("--ttl", action="store", required=False, default=10, help="Refresh token TTL")
        parser.add_argument(
            "--local",
            action="store_true",
            required=False,
            default=False,
            help="Run locally and read secrets from k8s cluster [dev only]",
        )


if __name__ == "__main__":
    SetupUIJwt.start()
