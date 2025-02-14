# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from django.utils.crypto import get_random_string
from jwcrypto.common import base64url_decode, base64url_encode
from jwcrypto.jwk import JWK, JWKSet

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenType

_logger = logging.getLogger(__name__)


_DEFAULT_ALG = "HS256"


@dataclass(frozen=True)
class JWTSecretKey:
    secret_key: str
    key_id: str
    algorithm: str = _DEFAULT_ALG

    @classmethod
    def create_new(cls, short_key: bool = False, algorithm: str | None = None) -> JWTSecretKey:
        key_id = f"ts:{int(utcnow().timestamp())}"
        # Temporarely we need to support shorter keys for JWT due to the limitation in the go JWT python library.
        # Once we migrate to a rust based remoting frontend, we can get rid of this workaround.
        return cls(
            secret_key=get_random_string(32 if short_key else 1024), key_id=key_id, algorithm=algorithm or _DEFAULT_ALG
        )

    @property
    def timestamp(self) -> int:
        return int(self.key_id[3:])

    def to_jwk(self) -> JWK:
        encoded_key = base64url_encode(self.secret_key)
        return JWK(alg=self.algorithm, kty="oct", kid=self.key_id, k=encoded_key)

    @classmethod
    def from_jwk_set_json(cls, jwk_set_json: str) -> tuple[JWTSecretKey, ...]:
        keys = []
        # Not using JWKSet.from_json() since it doesn't guarantee order (since JWKSet is using a python set internally).
        for jwk_json in json.loads(jwk_set_json)["keys"]:
            jwk = JWK(**jwk_json)
            secret_key = base64url_decode(jwk["k"]).decode()
            keys.append(cls(key_id=jwk["kid"], secret_key=secret_key, algorithm=jwk["alg"]))
        return tuple(keys)


@dataclass(frozen=True)
class JWTSecretData:
    _SECRET_NAME = "jwt-auth-secret-key"
    refresh_token_keys: tuple[JWTSecretKey, ...]
    access_token_keys: tuple[JWTSecretKey, ...]

    @classmethod
    def from_jwk_set_json(
        cls, *, refresh_token_jwk_set_json: str | None = None, access_token_jwk_set_json: str | None = None
    ) -> JWTSecretData:
        refresh_token_keys = (
            JWTSecretKey.from_jwk_set_json(refresh_token_jwk_set_json) if refresh_token_jwk_set_json else tuple()
        )
        access_token_keys = (
            JWTSecretKey.from_jwk_set_json(access_token_jwk_set_json) if access_token_jwk_set_json else tuple()
        )
        return cls(refresh_token_keys=refresh_token_keys, access_token_keys=access_token_keys)

    @classmethod
    def load(cls, json_data: dict) -> JWTSecretData:
        refresh_token_keys = tuple(JWTSecretKey(**json_key) for json_key in json_data["refresh_token_keys"])
        access_token_keys = tuple(JWTSecretKey(**json_key) for json_key in json_data["access_token_keys"])
        return cls(refresh_token_keys=refresh_token_keys, access_token_keys=access_token_keys)

    @classmethod
    def read_settings(cls, toolchain_env, secrets_reader) -> JWTSecretData | None:
        if not toolchain_env.is_prod_or_dev:
            return None
        json_secret_data = secrets_reader.get_json_secret_or_raise(cls._SECRET_NAME)
        secret_data = cls.load(json_secret_data)
        _logger.info(f"Load ({secret_data}) from {cls._SECRET_NAME} via {secrets_reader}")
        return secret_data

    @classmethod
    def create_new(cls) -> JWTSecretData:
        refresh_token_keys = (JWTSecretKey.create_new(),)
        access_token_keys = (JWTSecretKey.create_new(),)
        return cls(refresh_token_keys=refresh_token_keys, access_token_keys=access_token_keys)

    @classmethod
    def create_for_tests_identical(cls, secret_key: str, key_id: str | None = None) -> JWTSecretData:
        key_id = key_id or f"ts:{int(utcnow().timestamp())}"
        refresh_token_keys = (JWTSecretKey(key_id=key_id, secret_key=secret_key),)
        access_token_keys = (JWTSecretKey(key_id=key_id, secret_key=secret_key),)
        return cls(refresh_token_keys=refresh_token_keys, access_token_keys=access_token_keys)

    @classmethod
    def create_for_tests(cls, secret_key: str, base_key_id: str | None = None) -> JWTSecretData:
        base_key_id = base_key_id or f":ts:{int(utcnow().timestamp())}"
        refresh_token_keys = (JWTSecretKey(key_id=f"rf:{base_key_id}", secret_key=f"refresh:{secret_key}"),)
        access_token_keys = (JWTSecretKey(key_id=f"ac:{base_key_id}", secret_key=f"access:{secret_key}"),)
        return cls(refresh_token_keys=refresh_token_keys, access_token_keys=access_token_keys)

    def get_for_key_id(self, key_id: str, token_type: AccessTokenType) -> JWTSecretKey | None:
        # TODO: we could be more efficient with a dict, but this list is short for now so NBD.
        for key in self._get_keys_for_type(token_type):
            if key.key_id == key_id:
                return key
        return None

    def get_current(self, token_type: AccessTokenType) -> JWTSecretKey:
        return self._get_keys_for_type(token_type)[0]

    def get_current_refresh_token_key(self) -> JWTSecretKey:
        return self.get_current(AccessTokenType.REFRESH_TOKEN)

    def get_current_access_token_key(self) -> JWTSecretKey:
        return self.get_current(AccessTokenType.ACCESS_TOKEN)

    def _get_keys_for_type(self, token_type: AccessTokenType) -> tuple[JWTSecretKey, ...]:
        if token_type == AccessTokenType.ACCESS_TOKEN:
            return self.access_token_keys
        if token_type == AccessTokenType.REFRESH_TOKEN:
            return self.refresh_token_keys
        raise ToolchainAssertion(f"Invalid token type {token_type}")

    def to_dict(self):
        data_dict = asdict(self)
        data_dict["refresh_token_keys"] = list(data_dict["refresh_token_keys"])
        data_dict["access_token_keys"] = list(data_dict["access_token_keys"])
        return data_dict

    def get_access_tokens_jwk_set_dict(self) -> dict:
        jwks = JWKSet()
        for key in self.access_token_keys:
            jwks.add(key.to_jwk())
        return jwks.export(private_keys=True, as_dict=True)

    def __str__(self) -> str:
        refresh_tokens_keys = ", ".join(key.key_id for key in self.refresh_token_keys)
        access_tokens_keys = ", ".join(key.key_id for key in self.access_token_keys)
        return f"JWTSecretData({refresh_tokens_keys=} {access_tokens_keys=})"
