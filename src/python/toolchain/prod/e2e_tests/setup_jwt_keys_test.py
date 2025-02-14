# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from pathlib import Path

import pytest
from jose import jwt
from jwcrypto.common import base64url_encode
from jwcrypto.jwk import JWK, JWKSet

from toolchain.base.datetime_tools import utcnow
from toolchain.prod.e2e_tests.setup_jwt_keys import JwtFormat, SetupJwtAccessKey
from toolchain.util.secret.secrets_accessor import LocalSecretsAccessor


class TestSetupJwtAccessKey:
    @pytest.fixture()
    def jwk(self) -> JWK:
        return JWK(kty="oct", kid="bania", alg="HS256", k=base64url_encode("lopper-riverside-park-frogger"))

    def get_tool(
        self, tmp_path: Path, jwk: JWK, customer: str, audience: str, jwt_format: JwtFormat = JwtFormat.TEXT
    ) -> SetupJwtAccessKey:
        secret_path = tmp_path / "secrets"
        key_set = JWKSet()
        key_set.add(jwk)
        secret_value = json.dumps(key_set.export(private_keys=True, as_dict=True))
        accessor = LocalSecretsAccessor.create_rotatable(secret_path.as_posix(), for_k8s_volume_reader=True)
        accessor.set_secret("jwk-access-token-keys", secret_value)
        tokens_path = tmp_path / "tokens" / "jerry.jwt"
        return SetupJwtAccessKey.create_for_args(
            audience=audience,
            customer=customer,
            path=tokens_path.as_posix(),
            secret_path=secret_path.as_posix(),
            format=jwt_format.value,
        )

    def load_token(self, tmp_path: Path) -> str:
        token_path = tmp_path / "tokens" / "jerry.jwt"
        assert token_path.exists()
        return token_path.read_text("utf8")

    def assert_text_token(self, tmp_path: Path, expected_claims: dict) -> None:
        token_data = self.load_token(tmp_path)
        self.assert_token(token_data, expected_claims)

    def assert_token(self, token_str: str, expected_claims: dict) -> None:
        claims = jwt.decode(
            token_str, key="lopper-riverside-park-frogger", algorithms=["HS256"], options=dict(verify_aud=False)
        )
        assert set(claims.keys()) == {
            "username",
            "iat",
            "toolchain_repo",
            "iss",
            "type",
            "toolchain_user",
            "toolchain_claims_ver",
            "exp",
            "aud",
            "toolchain_customer",
        }
        issued_at = claims.pop("iat")
        now = utcnow()
        assert issued_at == pytest.approx(now.timestamp(), rel=2)
        assert claims.pop("exp") == issued_at + 180
        assert expected_claims == claims

    def test_create_cache_rw_token(self, jwk: JWK, tmp_path: Path) -> None:
        tool = self.get_tool(tmp_path, jwk, customer="pole", audience="cache_rw")
        assert tool.run() == 0
        self.assert_text_token(
            tmp_path,
            {
                "aud": ["cache_rw"],
                "username": "seinfeld",
                "type": "access",
                "toolchain_user": "hello-newman",
                "toolchain_repo": "gold-jerry-gold",
                "toolchain_customer": "pole",
                "iss": "toolchain",
                "toolchain_claims_ver": 2,
            },
        )

    def test_create_cache_token(self, jwk: JWK, tmp_path: Path) -> None:
        tool = self.get_tool(tmp_path, jwk, customer="pole", audience="cache_rw,cache_ro")
        assert tool.run() == 0
        self.assert_text_token(
            tmp_path,
            {
                "aud": ["cache_ro", "cache_rw"],
                "username": "seinfeld",
                "type": "access",
                "toolchain_user": "hello-newman",
                "toolchain_repo": "gold-jerry-gold",
                "toolchain_customer": "pole",
                "iss": "toolchain",
                "toolchain_claims_ver": 2,
            },
        )

    def test_create_buildsense_token(self, jwk: JWK, tmp_path: Path) -> None:
        tool = self.get_tool(tmp_path, jwk, customer="pole", audience="buildsense", jwt_format=JwtFormat.JSON)
        assert tool.run() == 0
        json_token = json.loads(self.load_token(tmp_path))
        assert json_token["customer_id"] == "pole"
        assert json_token["repo_id"] == "gold-jerry-gold"
        assert json_token["customer_id"] == "pole"
        self.assert_token(
            json_token["access_token"],
            {
                "aud": ["buildsense"],
                "username": "seinfeld",
                "type": "access",
                "toolchain_user": "hello-newman",
                "toolchain_repo": "gold-jerry-gold",
                "toolchain_customer": "pole",
                "iss": "toolchain",
                "toolchain_claims_ver": 2,
            },
        )

    def test_invalid_audience(self, jwk: JWK, tmp_path: Path) -> None:
        with pytest.raises(KeyError, match="'jerry'"):
            self.get_tool(tmp_path, jwk, customer="pole", audience="cache_rw,jerry")

        with pytest.raises(KeyError, match="'frogger'"):
            self.get_tool(tmp_path, jwk, customer="pole", audience="frogger")
