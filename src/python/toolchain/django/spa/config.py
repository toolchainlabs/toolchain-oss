# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional, cast
from urllib.parse import urlunsplit

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.util.config.app_config import AppConfig
from toolchain.util.config.kubernetes_env import KubernetesEnv

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StaticContentConfig:
    DEV_BUCKET = "assets-dev.us-east-1.toolchain.com"
    static_url: str
    domains: tuple[str, ...]
    version: str
    timestamp: str  # iso format datetime, see deploy_fronted.py
    commit_sha: str
    bundles: tuple[str, ...]
    private_key: RSAPrivateKey | None = None
    public_key_id: str | None = None

    @classmethod
    def for_test(cls) -> StaticContentConfig:
        return cls(
            static_url="https://babka.com/chocolate",
            domains=("babka.com",),
            version="cinnamon",
            timestamp="2020-10-22T06:08:57+00:00",
            commit_sha="jerk-store",
            bundles=("runtime.js", "vendors~main.js", "main.js"),
        )

    @classmethod
    def get_dev_asset_config(cls, app_name: str, k8s_env: KubernetesEnv, namespace: str | None) -> dict:
        namespaces = [k8s_env.namespace] if k8s_env.is_running_in_kubernetes else []
        if not namespaces and namespace:
            namespaces.append(namespace)
        namespaces.append("shared")
        return {
            "bucket": cls.DEV_BUCKET,
            "keys": [f"dev/{app_name}/{ns}/{ns}.json" for ns in namespaces],
        }

    @classmethod
    def from_config(
        cls,
        *,
        app_name: str,
        k8s_env: KubernetesEnv,
        toolchain_env: ToolchainEnv,
        aws_region: str,
        config: AppConfig,
        secrets_reader=None,
        namespace: str | None = None,
    ) -> StaticContentConfig:
        is_prod = toolchain_env.is_prod  # type: ignore[attr-defined]
        asset_config = cast(Optional[dict], config.get("STATIC_ASSETS_CONFIG"))
        if not asset_config:
            if is_prod:
                raise ToolchainAssertion("STATIC_ASSETS_CONFIG must be specified for production")
            asset_config = cls.get_dev_asset_config(app_name, k8s_env, namespace=namespace)
        bucket = asset_config["bucket"]
        s3 = S3(aws_region)
        version_path = find_current_version(s3, bucket, asset_config["keys"])
        manifest = json.loads(s3.get_content(bucket=bucket, key=version_path))
        domain = manifest.get("domain", f"{bucket}.s3.amazonaws.com")
        scheme = "https" if is_prod else "http"
        # Backward compatibility, existing versions bundles don't end with '.js'
        bundles = tuple(name if name.endswith(".js") else f"{name}.js" for name in manifest["bundles"])
        cfg = cls(
            static_url=urlunsplit((scheme, domain, manifest["path"], "", "")),
            domains=(domain,),
            version=manifest["version"],
            timestamp=manifest["timestamp"],
            commit_sha=manifest["commit_sha"],
            private_key=_load_private_key(secrets_reader),
            public_key_id=asset_config.get("public_key_id"),
            bundles=bundles,
        )
        _logger.info(
            f"Serving SPA from: {cfg.domains} url={cfg.static_url} timestamp={cfg.timestamp} bundles={cfg.bundles}"
        )
        return cfg

    @property
    def is_local(self) -> bool:
        return self.version == ""

    @property
    def with_source_maps(self) -> bool:
        return all([self.private_key, self.public_key_id, self.version, self.domains])


def find_current_version(s3, bucket, keys) -> str:
    for key in keys:
        if not s3.exists(bucket=bucket, key=key):
            continue
        current_version_data = json.loads(s3.get_content(bucket=bucket, key=key))
        return current_version_data["current"]["manifest_path"]
    raise ToolchainAssertion(f"No current versions files available. looked under {bucket=} {keys=}")


def _load_private_key(secrets_reader) -> RSAPrivateKey | None:
    if not secrets_reader:
        return None
    private_key = secrets_reader.get_secret("source-maps-private-key")
    if not private_key:  # We don't have a private key in dev, and currently it is optional in prod
        return None
    return serialization.load_pem_private_key(private_key.encode(), password=None, backend=default_backend())  # type: ignore[return-value]
