# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.django.spa.config import StaticContentConfig
from toolchain.util.config.app_config import AppConfig
from toolchain.util.config.kubernetes_env import KubernetesEnv
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor, SecretsAccessor

_REGION = "ap-northeast-2"


class TestStaticContentConfig:
    _BUCKET = "fake-assets-bucket-test"

    @pytest.fixture()
    def secrets_accessor(self) -> SecretsAccessor:
        DummySecretsAccessor._instance = None
        return DummySecretsAccessor.create_rotatable()

    def _save_json(self, key: str, data: dict) -> None:
        s3 = S3(_REGION)
        s3.upload_json_str(bucket=self._BUCKET, key=key, json_str=json.dumps(data))

    @pytest.fixture(autouse=True)
    def _start_moto(self, monkeypatch):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            monkeypatch.setattr(StaticContentConfig, "DEV_BUCKET", self._BUCKET)
            yield

    @pytest.fixture()
    def local_dev_env(self) -> KubernetesEnv:
        return KubernetesEnv.from_config(AppConfig({"TOOLCHAIN_ENV": "toolchain_dev"}))

    @pytest.fixture()
    def prod_env(self) -> KubernetesEnv:
        return KubernetesEnv.from_config(AppConfig({"TOOLCHAIN_ENV": "toolchain_prod", "K8S_POD_NAMESPACE": "prod"}))

    @pytest.fixture()
    def k8s_dev_env(self) -> KubernetesEnv:
        return KubernetesEnv.from_config(AppConfig({"TOOLCHAIN_ENV": "toolchain_dev", "K8S_POD_NAMESPACE": "jerry"}))

    def test_for_prod_no_configs(self, prod_env: KubernetesEnv) -> None:
        with pytest.raises(ToolchainAssertion, match="STATIC_ASSETS_CONFIG must be specified for production"):
            StaticContentConfig.from_config(
                k8s_env=prod_env,
                toolchain_env=ToolchainEnv.PROD,  # type: ignore[attr-defined]
                aws_region=_REGION,
                config=AppConfig({}),
                app_name="frontend",
            )

    def test_for_dev_local_no_versions(self, local_dev_env: KubernetesEnv) -> None:
        with pytest.raises(ToolchainAssertion, match="No current versions files available"):
            StaticContentConfig.from_config(
                k8s_env=local_dev_env,
                toolchain_env=ToolchainEnv.DEV,  # type: ignore[attr-defined]
                aws_region=_REGION,
                config=AppConfig({}),
                app_name="frontend",
            )

    def test_for_local_dev(self, local_dev_env: KubernetesEnv) -> None:
        manifest = {
            "path": "/dev/spa/versions/jerry_bundles/",
            "version": "big-salad",
            "timestamp": "reggie's",
            "commit_sha": "bob",
            "bundles": ["runtime", "vendors~main", "main"],
        }

        self._setup_version(
            manifest,
            manifest_path="dev/frontend/shared/versions/benes_version.json",
            version_path="dev/frontend/shared/shared.json",
        )
        cfg = StaticContentConfig.from_config(
            k8s_env=local_dev_env,
            toolchain_env=ToolchainEnv.DEV,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=AppConfig({}),
            app_name="frontend",
        )
        assert cfg.domains == ("fake-assets-bucket-test.s3.amazonaws.com",)
        assert cfg.version == "big-salad"
        assert cfg.timestamp == "reggie's"
        assert cfg.static_url == "http://fake-assets-bucket-test.s3.amazonaws.com/dev/spa/versions/jerry_bundles/"
        assert cfg.private_key is None
        assert cfg.public_key_id is None
        assert cfg.with_source_maps is False
        assert cfg.commit_sha == "bob"

    def _setup_version(self, manifest: dict, manifest_path: str, version_path: str) -> None:
        self._save_json(manifest_path, manifest)
        self._save_json(version_path, {"current": {"manifest_path": manifest_path}})

    def _setup_versions(self, domain: str | None = None, commit_sha: str | None = None) -> None:
        manifest_1 = {
            "path": "/spa/versions/benes_bundles/",
            "version": "big-salad",
            "timestamp": "reggie's",
            "commit_sha": "bob",
            "bundles": ["runtime", "vendors~main", "main"],
        }
        if commit_sha:
            manifest_1["commit_sha"] = "you-slept-with-the-groom"
        self._setup_version(
            manifest_1, manifest_path="/spa/versions/benes_version.json", version_path="/spa/benes.json"
        )
        manifest_2 = {
            "path": "/spa/bundles/elaine_assets/",
            "version": "dance",
            "timestamp": "elaine",
            "commit_sha": "festivus",
            "bundles": ["runtime", "vendors~main", "main"],
        }
        if domain:
            manifest_2["domain"] = domain
        if commit_sha:
            manifest_2["commit_sha"] = commit_sha
        self._setup_version(
            manifest_2, manifest_path="/spa/versions/elaine_version.json", version_path="/spa/elaine.json"
        )

    def test_dev_config_read_s3(self, k8s_dev_env: KubernetesEnv) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/benes.json", "/spa/elaine.json"],
                }
            }
        )
        self._setup_versions(commit_sha="caffe-latte")
        cfg = StaticContentConfig.from_config(
            k8s_env=k8s_dev_env,
            toolchain_env=ToolchainEnv.DEV,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=app_cfg,
            app_name="frontend",
        )
        assert cfg.domains == ("fake-assets-bucket-test.s3.amazonaws.com",)
        assert cfg.version == "big-salad"
        assert cfg.timestamp == "reggie's"
        assert cfg.static_url == "http://fake-assets-bucket-test.s3.amazonaws.com/spa/versions/benes_bundles/"
        assert cfg.private_key is None
        assert cfg.public_key_id is None
        assert cfg.with_source_maps is False
        assert cfg.commit_sha == "you-slept-with-the-groom"

    def test_prod_config_read_s3(self, prod_env: KubernetesEnv) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/benes.json", "/spa/elaine.json"],
                }
            }
        )
        self._setup_versions()
        cfg = StaticContentConfig.from_config(
            k8s_env=prod_env,
            toolchain_env=ToolchainEnv.PROD,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=app_cfg,
            app_name="frontend",
        )
        assert cfg.domains == ("fake-assets-bucket-test.s3.amazonaws.com",)
        assert cfg.version == "big-salad"
        assert cfg.timestamp == "reggie's"
        assert cfg.static_url == "https://fake-assets-bucket-test.s3.amazonaws.com/spa/versions/benes_bundles/"
        assert cfg.private_key is None
        assert cfg.public_key_id is None
        assert cfg.with_source_maps is False
        assert cfg.commit_sha == "bob"

    def test_prod_config_with_custom_domain(self, secrets_accessor: SecretsAccessor, prod_env: KubernetesEnv) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/elaine.json", "/spa/benes.json"],
                }
            }
        )
        self._setup_versions(domain="jerry.newman.com", commit_sha="the-ocean-called")
        cfg = StaticContentConfig.from_config(
            k8s_env=prod_env,
            toolchain_env=ToolchainEnv.PROD,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=app_cfg,
            secrets_reader=secrets_accessor,
            app_name="frontend",
        )
        assert cfg.domains == ("jerry.newman.com",)
        assert cfg.version == "dance"
        assert cfg.timestamp == "elaine"
        assert cfg.static_url == "https://jerry.newman.com/spa/bundles/elaine_assets/"
        assert cfg.private_key is None
        assert cfg.public_key_id is None
        assert cfg.with_source_maps is False
        assert cfg.commit_sha == "the-ocean-called"

    def test_dev_config_read_s3_skip_missing_key(
        self, secrets_accessor: SecretsAccessor, prod_env: KubernetesEnv
    ) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/jerry.json", "/spa/elaine.json", "/spa/benes.json"],
                }
            }
        )
        self._setup_versions()
        cfg = StaticContentConfig.from_config(
            k8s_env=prod_env,
            toolchain_env=ToolchainEnv.DEV,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=app_cfg,
            secrets_reader=secrets_accessor,
            app_name="frontend",
        )
        assert cfg.domains == ("fake-assets-bucket-test.s3.amazonaws.com",)
        assert cfg.version == "dance"
        assert cfg.timestamp == "elaine"
        assert cfg.static_url == "http://fake-assets-bucket-test.s3.amazonaws.com/spa/bundles/elaine_assets/"
        assert cfg.private_key is None
        assert cfg.public_key_id is None
        assert cfg.with_source_maps is False

    def test_prod_config_read_s3_skip_missing_key(self, prod_env: KubernetesEnv) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/jerry.json", "/spa/elaine.json", "/spa/benes.json"],
                }
            }
        )
        self._setup_versions()
        cfg = StaticContentConfig.from_config(
            k8s_env=prod_env,
            toolchain_env=ToolchainEnv.PROD,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=app_cfg,
            app_name="frontend",
        )
        assert cfg.domains == ("fake-assets-bucket-test.s3.amazonaws.com",)
        assert cfg.version == "dance"
        assert cfg.timestamp == "elaine"
        assert cfg.static_url == "https://fake-assets-bucket-test.s3.amazonaws.com/spa/bundles/elaine_assets/"
        assert cfg.private_key is None
        assert cfg.public_key_id is None
        assert cfg.with_source_maps is False
        assert cfg.commit_sha == "festivus"

    @pytest.mark.parametrize("tc_env", [ToolchainEnv.DEV, ToolchainEnv.PROD])  # type: ignore[attr-defined]
    def test_config_read_s3_no_keys(self, tc_env: ToolchainEnv) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/jerry.json", "/spa/elaine.json", "/spa/benes.json"],
                }
            }
        )
        k8s_env = KubernetesEnv.from_config(AppConfig({"TOOLCHAIN_ENV": tc_env.value, "K8S_POD_NAMESPACE": "keith"}))
        with pytest.raises(ToolchainAssertion, match="No current versions files available"):
            StaticContentConfig.from_config(
                k8s_env=k8s_env,
                toolchain_env=tc_env,
                aws_region=_REGION,
                config=app_cfg,
                app_name="frontend",
            )

    def test_prod_config_with_source_maps(self, secrets_accessor: SecretsAccessor, prod_env: KubernetesEnv) -> None:
        app_cfg = AppConfig(
            {
                "STATIC_ASSETS_CONFIG": {
                    "public_key_id": "festivus",
                    "bucket": "fake-assets-bucket-test",
                    "keys": ["/spa/elaine.json", "/spa/benes.json"],
                }
            }
        )
        private_key = generate_private_key(backend=default_backend(), public_exponent=65537, key_size=1024)
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        secrets_accessor.set_secret("source-maps-private-key", private_key_bytes.decode())
        self._setup_versions(domain="jerry.newman.com")
        cfg = StaticContentConfig.from_config(
            k8s_env=prod_env,
            toolchain_env=ToolchainEnv.PROD,  # type: ignore[attr-defined]
            aws_region=_REGION,
            config=app_cfg,
            secrets_reader=secrets_accessor,
            app_name="frontend",
        )
        assert cfg.domains == ("jerry.newman.com",)
        assert cfg.version == "dance"
        assert cfg.timestamp == "elaine"
        assert cfg.static_url == "https://jerry.newman.com/spa/bundles/elaine_assets/"
        assert cfg.with_source_maps is True
        assert cfg.private_key is not None
        assert cfg.private_key.key_size == 1024
        assert cfg.public_key_id == "festivus"
