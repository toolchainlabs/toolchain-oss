# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

from toolchain.constants import ToolchainEnv


@dataclass(frozen=True)
class AppDescriptor:
    key: str
    name: str
    description: str

    @classmethod
    def for_env(cls, tc_env: ToolchainEnv) -> AppDescriptor:
        return cls.for_dev() if tc_env.is_dev else cls.for_prod()  # type: ignore[attr-defined]

    @classmethod
    def for_dev(cls):
        return cls(key="toolchain-dev", name="Toolchain Dev App", description="Toolchain Dev App")

    @classmethod
    def for_prod(cls):
        return cls(key="toolchain", name="Toolchain", description="Toolchain Build system")


@dataclass(frozen=True)
class BitbucketIntegrationConfig:
    descriptor: AppDescriptor
    client_id: str
    secret: str
    install_link: str

    @classmethod
    def from_secrets_and_config(cls, tc_env: ToolchainEnv, config, secrets_reader) -> BitbucketIntegrationConfig:
        bitbucket_secret = secrets_reader.get_json_secret_or_raise("bitbucket-app-creds")
        descriptor = AppDescriptor.for_env(tc_env)
        install_link = f"https://bitbucket.org/site/addons/authorize?addon_key={descriptor.key}"
        return cls(
            descriptor=descriptor,
            client_id=bitbucket_secret["APP_CLIENT_ID"],
            secret=bitbucket_secret["APP_SECRET"],
            install_link=install_link,
        )
