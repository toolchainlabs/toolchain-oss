# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from unittest import mock

from jwcrypto.common import base64url_encode

from toolchain.constants import ToolchainEnv
from toolchain.users.jwt.keys import JWTSecretData, JWTSecretKey


class TestJWTSecretData:
    def test_read_settings(self):
        reader = mock.MagicMock()
        reader.get_json_secret_or_raise.return_value = {
            "algorithm": "feats of strength",
            "refresh_token_keys": [{"key_id": "ts:874928743", "secret_key": "I find tinsel distracting"}],
            "access_token_keys": [{"key_id": "ts:111111111", "secret_key": "gold jerry gold"}],
        }
        assert JWTSecretData.read_settings(ToolchainEnv.COLLECTSTATIC, reader) is None
        assert JWTSecretData.read_settings(ToolchainEnv.TEST, reader) is None
        assert reader.get_json_secret_or_raise.call_count == 0
        for tc_env in [ToolchainEnv.PROD, ToolchainEnv.DEV]:
            reader.get_json_secret_or_raise.reset_mock()
            jwt_settings = JWTSecretData.read_settings(tc_env, reader)
            assert reader.get_json_secret_or_raise.call_count == 1
            reader.get_json_secret_or_raise.assert_called_once_with("jwt-auth-secret-key")
            assert len(jwt_settings.refresh_token_keys) == 1
            assert len(jwt_settings.access_token_keys) == 1
            assert jwt_settings.refresh_token_keys[0].key_id == "ts:874928743"
            assert jwt_settings.refresh_token_keys[0].timestamp == 874928743
            assert jwt_settings.refresh_token_keys[0].secret_key == "I find tinsel distracting"
            assert jwt_settings.access_token_keys[0].key_id == "ts:111111111"
            assert jwt_settings.access_token_keys[0].secret_key == "gold jerry gold"
            assert jwt_settings.access_token_keys[0].timestamp == 111111111
            assert jwt_settings.access_token_keys[0].algorithm == "HS256"
            assert jwt_settings.refresh_token_keys[0].algorithm == "HS256"
            assert jwt_settings.to_dict() == {
                "refresh_token_keys": [
                    {"secret_key": "I find tinsel distracting", "key_id": "ts:874928743", "algorithm": "HS256"}
                ],
                "access_token_keys": [
                    {"secret_key": "gold jerry gold", "key_id": "ts:111111111", "algorithm": "HS256"}
                ],
            }

    def test_get_access_tokens_jwk_set_dict(self) -> None:
        data = JWTSecretData.create_new()
        access_token_key = data.access_token_keys[0]
        jwk_set_dict = data.get_access_tokens_jwk_set_dict()
        assert jwk_set_dict == {
            "keys": [
                {
                    "kty": "oct",
                    "alg": "HS256",
                    "kid": access_token_key.key_id,
                    "k": base64url_encode(access_token_key.secret_key),
                }
            ]
        }

    def test_load_access_tokens_only_from_jwk(self) -> None:
        jwks = json.dumps(
            {
                "keys": [
                    {
                        "alg": "HS256",
                        "kty": "oct",
                        "kid": "mandelbaum",
                        "k": base64url_encode("when you control the mail, you control information"),
                    },
                    {
                        "alg": "HS256",
                        "kty": "oct",
                        "kid": "mole",
                        "k": base64url_encode("no-soup-for-you-come-back-one-year"),
                    },
                ]
            }
        )
        key_data = JWTSecretData.from_jwk_set_json(access_token_jwk_set_json=jwks)
        assert key_data.refresh_token_keys == tuple()
        assert len(key_data.access_token_keys) == 2
        key = key_data.get_current_access_token_key()
        assert key.key_id == "mandelbaum"
        assert key.algorithm == "HS256"
        assert key.secret_key == "when you control the mail, you control information"


class TestJWTSecretKey:
    def test_jwk(self) -> None:
        key = JWTSecretKey.create_new()
        jwk = key.to_jwk()
        assert jwk["kid"] == key.key_id
        assert jwk["kty"] == "oct"
        assert jwk.is_symmetric is True
        assert jwk.has_private is False
        assert jwk.has_public is False
        assert jwk.get_op_key(operation="sign") == base64url_encode(key.secret_key)
        assert jwk.get_op_key(operation="verify") == base64url_encode(key.secret_key)
        assert jwk.export(as_dict=True) == {
            "alg": "HS256",
            "kty": "oct",
            "kid": key.key_id,
            "k": base64url_encode(key.secret_key),
        }
