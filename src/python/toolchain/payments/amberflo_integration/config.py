# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

from toolchain.constants import ToolchainEnv


@dataclass(frozen=True)
class AmberFloConfiguration:
    api_key: str
    env_name: str

    @classmethod
    def create(cls, toolchain_env: ToolchainEnv, secrets_reader) -> AmberFloConfiguration:
        api_key = secrets_reader.get_json_secret_or_raise("amberflo-integration")["api_key"]
        env_name = toolchain_env.get_env_name() if toolchain_env.is_dev else "prod_v1"  # type: ignore[attr-defined]
        return cls(api_key=api_key, env_name=env_name)
