# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import json
from pathlib import Path

import pytest
from moto import mock_s3, mock_secretsmanager

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import TEST_REGION, create_s3_bucket
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.prod.installs.deploy_frontend import BuildAndDeployToolchainSPA
from toolchain.prod.tools.deploy_notifications import Deployer
from toolchain.util.prod.chat_client_test import create_fake_slack_webhook_secret


class TestBuildAndDeployToolchainSPA:
    _BUCKET = "fake-assets-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3(), mock_secretsmanager():
            create_fake_slack_webhook_secret()
            create_s3_bucket(self._BUCKET)
            yield

    def _create_deploy(self, is_prod: bool = False) -> BuildAndDeployToolchainSPA:
        env_name = "prod" if is_prod else "dev"
        base_key = f"{env_name}/frontend"
        if not is_prod:
            base_key = f"{base_key}/newman"
        return BuildAndDeployToolchainSPA.create(
            aws_region=TEST_REGION,
            bucket=self._BUCKET,
            base_key=base_key,
            tc_env=ToolchainEnv.PROD if is_prod else ToolchainEnv.DEV,  # type: ignore[attr-defined]
            deployer=Deployer(user="Elaine", machine="cosmo"),
            cluster=None,  # type: ignore[arg-type]
        )

    def _create_assets(self, tmp_path: Path) -> Path:
        spa_dir = tmp_path / "fake_spa"
        spa_dir.mkdir()
        (spa_dir / "test.js").write_text("Look to the cookie", encoding="utf-8")
        (spa_dir / "puffy.png").write_bytes(b"I don't want to be a pirate")
        (spa_dir / "8ball.svg").write_bytes(b"You got a question, ask the 8-ball")
        return spa_dir

    def _create_manifest(self, key: str) -> None:
        s3 = S3(TEST_REGION)
        s3.upload_json_str(
            self._BUCKET,
            key,
            json_str=json.dumps(
                {
                    "manifest_version": "1",
                    "version": "all-sides-point-to-yes",
                    "path": "prod/frontend/newman/bundles/all-sides-point-to-yes/spa/",
                    "deployer": "Elaine @ cosmo",
                    "timestamp": "2020-10-23T21:44:21+00:00",
                }
            ),
        )

    def _load_json(self, key: str) -> dict:
        s3 = S3(TEST_REGION)
        data, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=key)
        assert content_type == "application/json"
        return json.loads(data)

    def _assert_spa_assets(self, base_location: str) -> None:
        s3 = S3(TEST_REGION)
        data, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=f"{base_location}/test.js")
        assert content_type == "application/javascript"
        assert data == b"Look to the cookie"
        data, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=f"{base_location}/puffy.png")
        assert content_type == "image/png"
        assert data == b"I don't want to be a pirate"
        data, content_type = s3.get_content_with_type(bucket=self._BUCKET, key=f"{base_location}/8ball.svg")
        assert content_type == "image/svg+xml"
        assert data == b"You got a question, ask the 8-ball"

    def test_upload_bundles(self, tmp_path: Path) -> None:
        deploy_fe = self._create_deploy()
        assets_dir = self._create_assets(tmp_path)
        asset_files = deploy_fe._get_files(assets_dir)
        summary = deploy_fe._s3_access.upload_bundles(
            asset_files=asset_files,
            version="all-sides-point-to-yes",
            timestamp=datetime.datetime(2020, 10, 26, 23, 55, 11, tzinfo=datetime.timezone.utc),
            domain=None,
            commit_sha="half-milk-half-coffee",
            deployer=deploy_fe._deployer.formatted_deployer,
            app_name="newman",
            bundles=(Path("jerry.js"), Path("kramer.js")),
        )
        assert summary is not None
        assert summary.manifest_key == "dev/frontend/newman/manifests/all-sides-point-to-yes.json"
        assert summary.commit_sha == "half-milk-half-coffee"
        assert self._load_json(summary.manifest_key) == {
            "manifest_version": "1",
            "version": "all-sides-point-to-yes",
            "path": "dev/frontend/newman/bundles/all-sides-point-to-yes/newman/",
            "deployer": "Elaine @ cosmo",
            "timestamp": "2020-10-26T23:55:11+00:00",
            "commit_sha": "half-milk-half-coffee",
            "bundles": ["jerry.js", "kramer.js"],
        }
        assert set(S3(TEST_REGION).keys_with_prefix(bucket=self._BUCKET, key_prefix="")) == {
            "dev/frontend/newman/bundles/all-sides-point-to-yes/newman/8ball.svg",
            "dev/frontend/newman/manifests/all-sides-point-to-yes.json",
            "dev/frontend/newman/bundles/all-sides-point-to-yes/newman/test.js",
            "dev/frontend/newman/bundles/all-sides-point-to-yes/newman/puffy.png",
            "dev/frontend/newman/bundles/all-sides-point-to-yes/newman/favicon.png",
            "dev/frontend/newman/bundles/all-sides-point-to-yes/newman/favicon.webp",
        }
        self._assert_spa_assets("dev/frontend/newman/bundles/all-sides-point-to-yes/newman")

    def test_no_current_version(self) -> None:
        manifest_key = "dev/frontend/newman/manifests/all-sides-point-to-yes.json"
        deploy_fe = self._create_deploy()
        deploy_fe._s3_access.update_current_version(namespace="pirate", new_version_manifest_key=manifest_key)
        assert self._load_json("dev/frontend/newman/pirate.json") == {
            "version": "1",
            "current": {
                "manifest_path": "dev/frontend/newman/manifests/all-sides-point-to-yes.json",
            },
            "previous": [],
        }

    def test_deploy_existing_current_version(self) -> None:
        s3 = S3(TEST_REGION)
        s3.upload_json_str(
            self._BUCKET,
            "dev/frontend/newman/superman.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "dev/frontend/newman/manifests/all-sides-point-to-yes.json",
                    },
                    "previous": [],
                }
            ),
        )
        deploy_fe = self._create_deploy()
        deploy_fe._s3_access.update_current_version(
            namespace="superman", new_version_manifest_key="dev/frontend/newman/manifests/pepsi.json"
        )
        assert self._load_json("dev/frontend/newman/superman.json") == {
            "version": "1",
            "current": {"manifest_path": "dev/frontend/newman/manifests/pepsi.json"},
            "previous": [
                {"manifest_path": "dev/frontend/newman/manifests/all-sides-point-to-yes.json", "rollback": False}
            ],
        }

    def test_rollback(self) -> None:
        s3 = S3(TEST_REGION)
        self._create_manifest("prod/frontend/manifests/pepsi.json")
        s3.upload_json_str(
            self._BUCKET,
            "prod/frontend/cookie.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "prod/frontend/manifests/bad-bad-version.json",
                    },
                    "previous": [
                        {"manifest_path": "prod/frontend/manifests/pepsi.json", "rollback": False},
                        {
                            "manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json",
                            "rollback": False,
                        },
                    ],
                }
            ),
        )
        deploy_fe = self._create_deploy(True)
        assert deploy_fe.rollback("cookie") is True
        assert self._load_json("prod/frontend/cookie.json") == {
            "version": "1",
            "current": {"manifest_path": "prod/frontend/manifests/pepsi.json"},
            "previous": [
                {"manifest_path": "prod/frontend/manifests/bad-bad-version.json", "rollback": True},
                {"manifest_path": "prod/frontend/manifests/pepsi.json", "rollback": False},
                {"manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json", "rollback": False},
            ],
        }

    def test_upload_prod_with_domain(self, tmp_path: Path) -> None:
        deploy_fe = self._create_deploy(True)
        assets_dir = self._create_assets(tmp_path)
        asset_files = deploy_fe._get_files(assets_dir)
        summary = deploy_fe._s3_access.upload_bundles(
            asset_files=asset_files,
            version="look-to-the-cookie",
            timestamp=datetime.datetime(2020, 11, 3, 18, 38, 59, tzinfo=datetime.timezone.utc),
            domain="cinnamon.babka.net",
            commit_sha="egregious-preposterous",
            deployer=deploy_fe._deployer.formatted_deployer,
            app_name="seinfeld",
            bundles=(Path("george.js"), Path("newman.js")),
        )
        assert summary is not None
        assert summary.manifest_key == "prod/frontend/manifests/look-to-the-cookie.json"
        assert summary.domain == "cinnamon.babka.net"
        assert summary.version == "look-to-the-cookie"
        assert summary.commit_sha == "egregious-preposterous"

        assert set(S3(TEST_REGION).keys_with_prefix(bucket=self._BUCKET, key_prefix="")) == {
            "prod/frontend/bundles/look-to-the-cookie/seinfeld/favicon.png",
            "prod/frontend/bundles/look-to-the-cookie/seinfeld/favicon.webp",
            "prod/frontend/bundles/look-to-the-cookie/seinfeld/puffy.png",
            "prod/frontend/bundles/look-to-the-cookie/seinfeld/test.js",
            "prod/frontend/manifests/look-to-the-cookie.json",
            "prod/frontend/bundles/look-to-the-cookie/seinfeld/8ball.svg",
        }
        self._assert_spa_assets("prod/frontend/bundles/look-to-the-cookie/seinfeld")
        assert self._load_json("prod/frontend/manifests/look-to-the-cookie.json") == {
            "manifest_version": "1",
            "version": "look-to-the-cookie",
            "commit_sha": "egregious-preposterous",
            "path": "look-to-the-cookie/seinfeld/",
            "deployer": "Elaine @ cosmo",
            "timestamp": "2020-11-03T18:38:59+00:00",
            "domain": "cinnamon.babka.net",
            "bundles": ["george.js", "newman.js"],
        }

    def test_promote_existing_target_version(self) -> None:
        deploy_fe = self._create_deploy(True)
        s3 = S3(TEST_REGION)
        s3.upload_json_str(
            self._BUCKET,
            "prod/frontend/no-bagel.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json",
                    },
                    "previous": [],
                }
            ),
        )
        s3.upload_json_str(
            self._BUCKET,
            "prod/frontend/babka.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "prod/frontend/manifests/puffy-shirt.json",
                    },
                    "previous": [],
                }
            ),
        )
        self._create_manifest("prod/frontend/manifests/all-sides-point-to-yes.json")
        assert deploy_fe.promote("no-bagel", "babka") is True
        assert self._load_json("prod/frontend/babka.json") == {
            "version": "1",
            "current": {"manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json"},
            "previous": [{"manifest_path": "prod/frontend/manifests/puffy-shirt.json", "rollback": False}],
        }

    def test_promote_no_version_in_target(self) -> None:
        deploy_fe = self._create_deploy(True)
        s3 = S3(TEST_REGION)
        s3.upload_json_str(
            self._BUCKET,
            "prod/frontend/no-bagel.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json",
                    },
                    "previous": [],
                }
            ),
        )
        self._create_manifest("prod/frontend/manifests/all-sides-point-to-yes.json")
        assert deploy_fe.promote("no-bagel", "chocolate") is True
        assert self._load_json("prod/frontend/chocolate.json") == {
            "version": "1",
            "current": {"manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json"},
            "previous": [],
        }

    def test_promote_bad_manifest_path(self) -> None:
        deploy_fe = self._create_deploy(True)
        s3 = S3(TEST_REGION)
        s3.upload_json_str(
            self._BUCKET,
            "prod/frontend/babka.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "prod/frontend/manifests/puffy-shirt.json",
                    },
                    "previous": [],
                }
            ),
        )
        s3.upload_json_str(
            self._BUCKET,
            "prod/frontend/no-bagel.json",
            json_str=json.dumps(
                {
                    "version": "1",
                    "current": {
                        "manifest_path": "prod/frontend/manifests/all-sides-point-to-yes.json",
                    },
                    "previous": [],
                }
            ),
        )
        with pytest.raises(ToolchainAssertion, match="Can't read current version for namespace: no-bagel"):
            deploy_fe.promote("no-bagel", "babka")
        assert self._load_json("prod/frontend/babka.json") == {
            "version": "1",
            "current": {"manifest_path": "prod/frontend/manifests/puffy-shirt.json"},
            "previous": [],
        }

    def test_promote_fail_no_version(self) -> None:
        deploy_fe = self._create_deploy(True)
        with pytest.raises(ToolchainAssertion, match="Can't read current version for namespace: babka"):
            deploy_fe.promote("babka", "chocolate")
