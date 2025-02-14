#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from argparse import ArgumentParser, Namespace
from enum import Enum, unique
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.prod.constants import JWKSET_SECRET_NAME
from toolchain.users.jwt.encoder import JWTEncoder
from toolchain.users.jwt.keys import JWTSecretData
from toolchain.util.secret.secrets_accessor import KubernetesVolumeSecretsReader

_logger = logging.getLogger(__name__)


@unique
class JwtFormat(Enum):
    TEXT = "text"
    JSON = "json"


class SetupJwtAccessKey(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"SetupJwtAccessKey arguments: {cmd_args}")
        self._toolchain_customer = cmd_args.customer
        self._audience = AccessTokenAudience.from_api_names(cmd_args.audience.split(","))
        self._secrets = KubernetesVolumeSecretsReader.create_rotatable(base_path=cmd_args.secret_path)
        self._path = Path(cmd_args.path or "/access_tokens/token.jwt")
        self._jwt_format = JwtFormat(cmd_args.format)

    def generate_jwt_access_token(self, encoder: JWTEncoder) -> None:
        audiences = self._audience.to_claim()
        now = utcnow()
        expires_at = now + datetime.timedelta(minutes=3)
        # We only use this tool w/ remote-cache & cas-load who doesn't care about those claims at this point.
        # I will be adding logic to populate those fields as I add more use cases for this tool.
        username = "seinfeld"
        user_api_id = "hello-newman"
        repo_id = "gold-jerry-gold"
        token_str = encoder.encode_access_token(
            expires_at=expires_at,
            issued_at=now,
            audience=self._audience,
            customer_id=self._toolchain_customer,
            is_restricted=False,
            username=username,
            user_api_id=user_api_id,
            repo_id=repo_id,
        )

        token = dict(
            access_token=token_str,
            expires_at=expires_at.isoformat(),
            user=username,
            repo=None,
            repo_id=repo_id,
            customer_id=self._toolchain_customer,
        )
        self._write_token(token, audiences)

    def _write_token(self, token: dict, audiences: list[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _logger.info(
            f"Saving JWT Access token to to {self._path.as_posix()} ({self._jwt_format.value}) with {audiences=} customer={self._toolchain_customer}"
        )
        if self._jwt_format == JwtFormat.TEXT:
            self._path.write_text(token["access_token"])
        elif self._jwt_format == JwtFormat.JSON:
            self._path.write_text(json.dumps(token))
        else:
            raise ToolchainAssertion(f"Unknown token format: {self._jwt_format}")

    def run(self) -> int:
        _logger.info(f"Load secret {JWKSET_SECRET_NAME} via {self._secrets}")
        secret = self._secrets.get_secret_or_raise(JWKSET_SECRET_NAME)
        secret_data = JWTSecretData.from_jwk_set_json(access_token_jwk_set_json=secret)
        encoder = JWTEncoder(secret_data)
        self.generate_jwt_access_token(encoder)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--customer", action="store", required=True, help="Value for toolchain_customer claim")
        parser.add_argument("--audience", action="store", required=True, help="Permissions (audience)")
        parser.add_argument("--path", action="store", required=True, help="full path to save token")
        parser.add_argument("--secret-path", action="store", required=False, help="secret path")
        parser.add_argument(
            "--format",
            action="store",
            default=JwtFormat.TEXT.value,
            choices=[fmt.value for fmt in JwtFormat],
            required=False,
            help="JWT file format",
        )


if __name__ == "__main__":
    SetupJwtAccessKey.start()
