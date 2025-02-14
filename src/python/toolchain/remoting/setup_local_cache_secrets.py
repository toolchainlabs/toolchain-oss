#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from jwcrypto.jwk import JWK, JWKSet
from jwcrypto.jwt import JWT

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.util.secret.secrets_accessor import LocalSecretsAccessor


class SetupLocalCacheSecrets(ToolchainBinary):
    SECRET_NAME = "jwtkeys"
    ALGORITHM = "HS256"
    KEY_ID = "k1"
    INSTANCE_NAME = "main"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._secrets = LocalSecretsAccessor.create_rotatable("prod/docker/remoting/local-cache/config")

    def get_or_create_key(self) -> JWK:
        secret = self._secrets.get_secret(self.SECRET_NAME)
        if secret:
            jwk_set = JWKSet.from_json(secret)
            return jwk_set.get_key(self.KEY_ID)

        jwk = JWK.generate(kty="oct", alg=self.ALGORITHM, kid=self.KEY_ID)
        jwk_set = JWKSet()
        jwk_set.add(jwk)
        jwk_set_json = jwk_set.export()
        self._secrets.set_secret(self.SECRET_NAME, jwk_set_json)
        return jwk

    def generate_jwt(self, key: JWK, name: str, audiences: Sequence[str]) -> None:
        now = utcnow()
        expires = now + timedelta(days=1)
        jwt = JWT(
            header={
                "alg": self.ALGORITHM,
                "kid": self.KEY_ID,
            },
            claims={
                "aud": audiences,
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
                "toolchain_customer": self.INSTANCE_NAME,
            },
        )
        jwt.make_signed_token(key)
        serialized_jwt = jwt.serialize()
        Path(f"prod/docker/remoting/local-cache/{name}.jwt").write_text(serialized_jwt)

    def maybe_sign_jwts(self, key: JWK) -> None:
        self.generate_jwt(key, "readonly", ["cache_ro"])
        self.generate_jwt(key, "readwrite", ["cache_rw"])

    def run(self) -> int:
        key = self.get_or_create_key()
        self.maybe_sign_jwts(key)
        return 0


if __name__ == "__main__":
    SetupLocalCacheSecrets.start()
