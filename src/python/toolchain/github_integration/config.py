# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

from toolchain.util.config.app_config import AppConfig


@dataclass(frozen=True)
class GithubIntegrationConfig:
    private_key: bytes
    app_id: str
    public_link: str

    @classmethod
    def from_secrets_and_config(cls, config: AppConfig, secrets_reader) -> GithubIntegrationConfig:
        private_key = secrets_reader.get_secret_or_raise("github-app-private-key")
        gh_cfg = config.get_config_section("GITHUB_CONFIG")
        link = gh_cfg["public_link"]
        if not link.endswith("/"):
            link = f"{link}/"
        return cls(private_key=private_key.encode(), app_id=gh_cfg["app_id"], public_link=link)

    def __str__(self) -> str:
        return f"GithubIntegrationConfig app_id={self.app_id} link={self.public_link}"

    def __repr__(self) -> str:
        return f"GithubIntegrationConfig(app_id={self.app_id}, public_link={self.public_link}, private_key=<redacted>)"
