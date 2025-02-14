# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import asdict, dataclass

from toolchain.constants import ToolchainEnv


@dataclass(frozen=True)
class AuthCookieConfig:
    name: str
    salt: str
    domain: str
    max_age_sec: int
    is_secure: bool

    @classmethod
    def for_tests(cls) -> AuthCookieConfig:
        tc_env = ToolchainEnv.DEV  # type: ignore
        return cls.create(toolchain_env=tc_env, salt="no-sup-for-you-come-back-one-year", domain="jerry.soup.private")

    @classmethod
    def create(cls, toolchain_env: ToolchainEnv, salt, domain: str) -> AuthCookieConfig:
        is_secure = toolchain_env.is_prod  # type: ignore
        return cls(name="toolshed", salt=salt, max_age_sec=3600 * 12, domain=domain, is_secure=is_secure)


@dataclass(frozen=True)
class DuoAuthConfig:
    secret_key: str
    application_key: str
    host: str

    @classmethod
    def from_secrets(cls, secrets_reader) -> DuoAuthConfig:
        duo_data = secrets_reader.get_json_secret_or_raise("duo-toolshed-app")
        duo_data.pop("integration_key", None)
        return cls(**duo_data)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @property
    def client_id(self) -> str:
        # See https://duo.com/docs/universal-prompt-update-guide#changes-to-support-the-universal-prompt (Renamed Application Fields)
        return self.application_key

    @property
    def client_secret(self) -> str:
        # See https://duo.com/docs/universal-prompt-update-guide#changes-to-support-the-universal-prompt (Renamed Application Fields)
        return self.secret_key
