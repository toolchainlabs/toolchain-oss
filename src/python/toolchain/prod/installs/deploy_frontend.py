# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import datetime
import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum, unique
from itertools import chain
from pathlib import Path

from humanize.filesize import naturalsize

from toolchain.aws.s3 import S3
from toolchain.base.fileutil import safe_delete_dir, walk_local_directory
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.application_api import KubernetesApplicationAPI
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.changes_helper import ChangeHelper, ChangeLog
from toolchain.prod.tools.deploy_notifications import Deployer, DeployNotifications, DeployType, FrontendDeployResult
from toolchain.util.prod.chat_client import Channel
from toolchain.util.prod.exceptions import NotConnectedToClusterError
from toolchain.util.prod.git_tools import InvalidCommitSha, get_commit_sha, get_last_commit_timestamp, get_version_tag
from toolchain.util.prod.sentry_api_client import SentryApiClient

_logger = logging.getLogger(__name__)


@unique
class AssetFileAssociation(Enum):
    RESOURCE = "resource"
    BUNDLE = "bundle"


@dataclass(frozen=True)
class AssetFile:
    Association = AssetFileAssociation
    relpath: str
    path: Path
    content_type: str
    size: int
    association: AssetFileAssociation

    @classmethod
    def create(
        cls, association: AssetFileAssociation, path: Path, content_type: str, relpath: str | None = None
    ) -> AssetFile:
        return cls(
            relpath=relpath or path.name,
            path=path,
            content_type=content_type,
            size=path.stat().st_size,
            association=association,
        )

    @property
    def is_bundle(self) -> bool:
        return self.association == AssetFileAssociation.BUNDLE


@dataclass(frozen=True)
class AssetFiles:
    files: tuple[AssetFile, ...]
    _JS_RELEASE_FILES = frozenset((".map", ".js"))

    @property
    def count(self) -> int:
        return len(self.files)

    def get_all(self) -> tuple[AssetFile, ...]:
        return self.files

    def get_total_size(self) -> int:
        return int(sum(fl.size for fl in self.files) / 1024)

    def get_js_release_files(self) -> tuple[Path, ...]:
        return tuple(file.path for file in self.files if file.path.suffix in self._JS_RELEASE_FILES and file.is_bundle)


@dataclass(frozen=True)
class BundleSummary:
    bucket: str
    assets_base_path: str
    manifest_key: str
    version: str
    domain: str | None
    commit_sha: str
    timestamp: datetime.datetime
    bundles: tuple[Path, ...]


class S3AssetsManager:
    _MAX_PREV_VERSIONS = 20
    _SCHEMA_VERSION = "1"
    _ASSETS_MAX_AGE = datetime.timedelta(days=30)

    def __init__(self, aws_region: str, bucket: str, base_key: str, make_public: bool) -> None:
        self._s3 = S3(region=aws_region)
        self._bucket = bucket
        self._base_key = base_key
        self._make_bundles_public = make_public
        self._manifests_base = f"{self._base_key}/manifests"
        self._bundle_base = f"{self._base_key}/bundles"

    def _get_current_version_data(self, namespace: str) -> tuple[str, dict | None]:
        key = f"{self._base_key}/{namespace}.json"
        version_json = self._s3.get_content_or_none(bucket=self._bucket, key=key)
        return (key, json.loads(version_json) if version_json else None)

    def get_current_version_manifest(self, namespace: str) -> BundleSummary | None:
        key, version_data = self._get_current_version_data(namespace)
        if not version_data:
            _logger.warning(f"No version for {namespace}: {key=}")
            return None
        manifest_key = version_data["current"]["manifest_path"]
        return self.load_manifest(manifest_key)

    def _save_json(self, key: str, data: dict) -> None:
        self._s3.upload_json_str(bucket=self._bucket, key=key, json_str=json.dumps(data, indent=4))

    def _create_manifest(
        self,
        version: str,
        timestamp: datetime.datetime,
        bundle_key_path: str,
        domain: str | None,
        commit_sha: str,
        deployer: str,
        bundles: tuple[Path, ...],
    ) -> str | None:
        manifest_key = f"{self._manifests_base}/{version}.json"
        manifest = {
            "manifest_version": self._SCHEMA_VERSION,
            "version": version,
            "path": bundle_key_path,
            "deployer": deployer,
            "timestamp": timestamp.isoformat(),
            "commit_sha": commit_sha,
            "bundles": [bundle.name for bundle in bundles],
        }
        if domain:
            manifest["domain"] = domain
        if self._s3.exists(bucket=self._bucket, key=manifest_key):
            _logger.error(f"Manifest already exists: {manifest_key}. abort")
            return None

        _logger.info(f"Upload manifest {manifest_key}")
        self._save_json(manifest_key, manifest)
        return manifest_key

    def purge_old_versions(self, namespace: str, dry_run: bool, threshold_days: int = 90) -> None:
        current_version = self.get_current_version_manifest(namespace)
        if not current_version:
            return
        deletion_threshold = current_version.timestamp - datetime.timedelta(days=threshold_days)
        candidates = self._get_versions_to_delete(namespace)
        delete_file_count = 0
        deleted_bytes_count = 0
        versions = 0
        for manifest_key in candidates:
            manifest = self.load_manifest(manifest_key)
            if not manifest:
                raise ToolchainAssertion(f"Failed to load manifest from {manifest_key}")
            if manifest.timestamp > deletion_threshold:
                continue
            files, size = self._delete_version(manifest, dry_run)
            versions += 1
            delete_file_count += files
            deleted_bytes_count += size
            _logger.info(f"delete {manifest_key=} {dry_run=}")
            if not dry_run:
                self._s3.delete_object(bucket=self._bucket, key=manifest_key)
        _logger.info(
            f"deleted {versions} versions, {delete_file_count} files, {naturalsize(deleted_bytes_count)}. {dry_run=}"
        )

    def _delete_version(self, manifest: BundleSummary, dry_run: bool) -> tuple[int, int]:
        files = 0
        total_size = 0
        for key_dict in self._s3.key_metadata_with_prefix(bucket=self._bucket, key_prefix=manifest.assets_base_path):
            files += 1
            size = key_dict["Size"]
            total_size += size
            key = key_dict["Key"]
            _logger.info(f"delete {key=} ({size=}) {dry_run=}")
            if not dry_run:
                self._s3.delete_object(bucket=self._bucket, key=key)
        return files, total_size

    def _get_versions_to_delete(self, namespace: str):
        in_use_manifests = self._get_manifests_paths(namespace)
        manifest_keys_iter = self._s3.keys_with_prefix(bucket=self._bucket, key_prefix=self._manifests_base)
        return [manifest_key for manifest_key in manifest_keys_iter if manifest_key not in in_use_manifests]

    def _get_manifests_paths(self, namespace: str) -> set[str]:
        _, version_data = self._get_current_version_data(namespace)
        if not version_data:
            raise ToolchainAssertion(f"Can't load current version data for {namespace}")
        manifests = {version_data["current"]["manifest_path"]}
        for prev_version in version_data["previous"]:
            manifests.add(prev_version["manifest_path"])
        return manifests

    def update_current_version(
        self, namespace: str, new_version_manifest_key: str, is_rollback: bool = False
    ) -> str | None:
        key, version_data = self._get_current_version_data(namespace)
        if version_data:
            previous_versions = version_data["previous"]
            current = version_data["current"]
            current["rollback"] = is_rollback
            prev_version_key = current["manifest_path"]
            previous_versions.insert(0, current)
        else:
            previous_versions = []
            prev_version_key = None
        new_ver_data = {
            "version": self._SCHEMA_VERSION,
            "current": {
                "manifest_path": new_version_manifest_key,
            },
            "previous": previous_versions[: self._MAX_PREV_VERSIONS],
        }
        _logger.info(
            f"Update {namespace} from version={prev_version_key or 'N/A'} to version={new_version_manifest_key} {'[rollback]' if is_rollback else ''}"
        )
        self._save_json(key, new_ver_data)
        return prev_version_key

    def get_previous_version(self, namespace: str) -> str | None:
        key, version_data = self._get_current_version_data(namespace)
        if not version_data:
            _logger.error(f"current version file is missing: {key=}")
            return None
        for prev_version in version_data["previous"]:
            if prev_version["rollback"] is True:
                continue
            return prev_version["manifest_path"]
        _logger.error(f"Couldn't find non-rolled back previous versions: {version_data=}")
        return None

    def load_manifest(self, manifest_key: str) -> BundleSummary | None:
        manifest_json = self._s3.get_content_or_none(bucket=self._bucket, key=manifest_key)
        if not manifest_json:
            return None
        manifest = json.loads(manifest_json)
        return BundleSummary(
            bucket=self._bucket,
            manifest_key=manifest_key,
            version=manifest["version"],
            domain=manifest.get("domain"),
            assets_base_path=manifest["path"],
            timestamp=datetime.datetime.fromisoformat(manifest["timestamp"]),
            # Optional fields because of backward compatibility
            commit_sha=manifest.get("commit_sha"),
            bundles=tuple(manifest.get("bundles", [])),
        )

    def upload_bundles(
        self,
        asset_files: AssetFiles,
        version: str,
        timestamp: datetime.datetime,
        domain: str | None,
        commit_sha: str,
        deployer: str,
        bundles: tuple[Path, ...],
        app_name: str,
    ) -> BundleSummary | None:
        relative_path = f"{version}/{app_name}/"
        bundle_key_path = f"{self._bundle_base}/{relative_path}"
        path_for_manifest = relative_path if domain else bundle_key_path
        manifest_key = self._create_manifest(
            version,
            timestamp,
            path_for_manifest,
            domain,
            commit_sha,
            deployer=deployer,
            bundles=bundles,
        )
        if not manifest_key:
            return None
        total_size = asset_files.get_total_size()
        _logger.info(f"Upload bundles files={asset_files.count} {total_size=:,}KB dest={bundle_key_path}")
        self._upload_assets(bundle_key_path, asset_files)
        return BundleSummary(
            bucket=self._bucket,
            manifest_key=manifest_key,
            timestamp=timestamp,
            assets_base_path=bundle_key_path,
            version=version,
            domain=domain,
            commit_sha=commit_sha,
            bundles=bundles,
        )

    def _upload_assets(self, base_key: str, asset_files: AssetFiles) -> None:
        for asset_file in asset_files.get_all():
            key = f"{base_key}{asset_file.relpath}"
            self._s3.upload_file(
                bucket=self._bucket,
                key=key,
                path=asset_file.path,
                content_type=asset_file.content_type,
                is_public=self._make_bundles_public,
                cache_max_age=self._ASSETS_MAX_AGE,
            )
            _logger.info(f"Uploaded {asset_file.path} to {key} ({asset_file.content_type})")


class BuildAndDeployFrontendApp(metaclass=abc.ABCMeta):
    _REACT_EMOJI = "reactjs"
    _CONTENT_TYPES = {
        "map": "application/json",
        "js": "application/javascript",
        "png": "image/png",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "css": "text/css",
        # Skip/don't upload those files
        "txt": None,
        "html": None,
        "json": None,
    }

    def __init__(
        self,
        *,
        aws_region: str,
        bucket: str,
        base_key: str,
        tc_env: ToolchainEnv,
        deployer: Deployer,
        cluster: KubernetesCluster | None,
        local_build_dir: Path,
        app_name: str,
        js_src_dir: Path,
        extra_files: tuple[Path, ...],
        backend_service: str,
        sentry_project_name: str,
    ) -> None:
        self._tc_env = tc_env
        self._aws_region = aws_region
        self._app_name = app_name
        self._js_src_dir = js_src_dir
        self._extra_files = extra_files
        self._backend_service = backend_service
        self._local_build_dir = local_build_dir
        self._sentry_project_name = sentry_project_name
        self._s3_access = S3AssetsManager(
            aws_region=aws_region,
            bucket=bucket,
            base_key=base_key,
            make_public=tc_env.is_dev,  # type: ignore[attr-defined]
        )
        self._deployer = deployer
        self._cluster = cluster
        self._notifications = DeployNotifications(
            is_prod=tc_env.is_prod, aws_region=aws_region, user=deployer.formatted_deployer  # type: ignore[attr-defined]
        )
        self._changes_helper = ChangeHelper.create(aws_region=aws_region)

    @abc.abstractmethod
    def get_bundle_names(self) -> tuple[Path, ...]:
        pass

    @property
    def local_build_dir(self) -> Path:
        return self._local_build_dir

    def check_cluster_connectivity(self) -> None:
        if not self._cluster:
            return
        if not ClusterAPI.is_connected_to_cluster(self._cluster):
            raise NotConnectedToClusterError(self._cluster)

    def _get_changelog(
        self, new_version: BundleSummary, prev_version_manifest_key: str | None, allow_invalid_commits: bool
    ) -> ChangeLog:
        if not prev_version_manifest_key:
            return ChangeLog.empty()
        prev_version_manifest = self._s3_access.load_manifest(prev_version_manifest_key)
        if not prev_version_manifest:
            _logger.warning(f"Can't load previous version manifest from: {prev_version_manifest_key}")
            return ChangeLog.empty()
        prev_version_commit_sha = prev_version_manifest.commit_sha
        try:
            if not prev_version_commit_sha or not new_version.commit_sha:
                _logger.warning(f"Missing commit sha. {prev_version_commit_sha=} {new_version.commit_sha=}")
                return ChangeLog.empty()
        except InvalidCommitSha as error:
            if not allow_invalid_commits:
                raise
            _logger.warning(f"Invalid commit sha. {error!r}")
            return ChangeLog.empty()

        return self._changes_helper.get_changes_for_paths(
            prev_version_commit_sha,
            new_version.commit_sha,
            changes_paths=(Path("src/node/yarn.lock"), self._js_src_dir),
        )

    def deploy(
        self,
        *,
        namespace: str,
        domain: str | None = None,
        skip_reload: bool = False,
        allow_invalid_commits: bool = False,
    ) -> bool:
        version = get_version_tag()
        commit_sha = get_commit_sha()
        timestamp = get_last_commit_timestamp()
        sentry_client = SentryApiClient.for_devops(
            aws_region=self._aws_region, toolchain_env=self._tc_env, prod_project=self._sentry_project_name
        )
        local_dir = self._build(version)
        asset_files = self._get_files(local_dir)
        js_release_files = asset_files.get_js_release_files()
        if not js_release_files:
            raise ToolchainAssertion("Missing JS release files from assets.")
        summary = self._s3_access.upload_bundles(
            asset_files,
            version,
            timestamp,
            domain,
            commit_sha,
            self._deployer.formatted_deployer,
            bundles=self.get_bundle_names(),
            app_name=self._app_name,
        )
        if not summary:
            return False
        prev_version_key = self._s3_access.update_current_version(
            namespace=namespace, new_version_manifest_key=summary.manifest_key
        )

        sentry_client.upload_js_release_files(
            release_name=version,
            commit_sha=commit_sha,
            release_files=js_release_files,
            base_local_dir=local_dir,
            base_version_path=f"{version}/{self._app_name}",
        )
        changelog = self._get_changelog(
            new_version=summary, prev_version_manifest_key=prev_version_key, allow_invalid_commits=allow_invalid_commits
        )
        if not skip_reload:
            self.reload_app(namespace=namespace)
            self._notify(namespace=namespace, summary=summary, changelog=changelog)
        _logger.info("All Done")
        return True

    def reload_app(self, *, namespace: str) -> None:
        if not self._cluster:
            return
        api = KubernetesApplicationAPI.for_cluster(cluster=self._cluster, namespace=namespace)
        api.rollout_restart_deployment(self._backend_service)

    def promote(self, source_namespace: str, target_namespace: str) -> bool:
        new_version_manifest = self._s3_access.get_current_version_manifest(source_namespace)
        if not new_version_manifest:
            raise ToolchainAssertion(f"Can't read current version for namespace: {source_namespace}")
        prev_version_key = self._s3_access.update_current_version(
            target_namespace, new_version_manifest_key=new_version_manifest.manifest_key
        )
        changelog = self._get_changelog(
            new_version=new_version_manifest, prev_version_manifest_key=prev_version_key, allow_invalid_commits=False
        )
        self.reload_app(namespace=target_namespace)
        self._notify(namespace=target_namespace, summary=new_version_manifest, changelog=changelog)
        return True

    def rollback(self, namespace: str, skip_reload: bool = False) -> bool:
        version_manifest_key = self._s3_access.get_previous_version(namespace)
        if not version_manifest_key:
            return False
        version_manifest = self._s3_access.load_manifest(version_manifest_key)
        if not version_manifest:
            _logger.warning(f"Can't load manifest from {version_manifest_key}")
            return False
        _logger.info(f"Rollback to: {version_manifest_key}")
        self._s3_access.update_current_version(
            namespace=namespace, new_version_manifest_key=version_manifest_key, is_rollback=True
        )
        if not skip_reload:
            self.reload_app(namespace=namespace)
            self._notify(namespace=namespace, summary=version_manifest, changelog=ChangeLog.empty())
        return True

    def purge_old_versions(self, namespace: str, dry_run: bool) -> bool:
        self._s3_access.purge_old_versions(namespace, dry_run)
        return True

    def _build(self, version: str) -> Path:
        safe_delete_dir(self.local_build_dir)
        src_dir = self._js_src_dir.as_posix()
        _logger.info(f"build bundles for: {self._app_name} version: {version} from {src_dir}")
        subprocess.check_output(["yarn", "build"], cwd=src_dir)
        return self.local_build_dir

    def _get_content_type(self, path: Path) -> str | None:
        return self._CONTENT_TYPES[path.suffix[1:]]

    def _add_files(self, fp: Path) -> list[AssetFile]:
        if fp.is_file():
            ct = self._get_content_type(fp)
            if not ct:
                return []
            return [AssetFile.create(AssetFile.Association.RESOURCE, fp, content_type=ct)]
        files = []
        for fl in fp.iterdir():
            files.extend(self._add_files(fl))
        return files

    def _get_files(self, local_dir: Path) -> AssetFiles:
        files = list(chain(*[self._add_files(fl) for fl in self._extra_files]))
        for relpath, path in walk_local_directory(local_dir):
            content_type = self._get_content_type(path)
            if not content_type:
                continue
            files.append(AssetFile.create(AssetFile.Association.BUNDLE, path, content_type, relpath=relpath.as_posix()))
        return AssetFiles(files=tuple(files))

    def _notify(self, *, namespace: str, summary: BundleSummary, changelog: ChangeLog) -> None:
        cluster = self._cluster
        if not cluster:
            return
        result = FrontendDeployResult(
            deploy_type=DeployType.FRONTEND,
            deployer=self._deployer,
            app=self._app_name,
            cluster=cluster,
            namespace=namespace,
            dry_run=False,
            version=summary.version,
            bucket=summary.bucket,
            domain=summary.domain or "N/A",
            manifest_key=summary.manifest_key,
            changes=changelog.get_changes(),
        )
        self._notifications.notify_deploy(result, quiet=False, channel=Channel.FRONTEND, emoji=self._REACT_EMOJI)


class BuildAndDeployToolchainSPA(BuildAndDeployFrontendApp):
    FAV_ICONS = (
        Path("src/python/toolchain/servicerouter/static/servicerouter/images/favicon.png"),
        Path("src/python/toolchain/servicerouter/static/servicerouter/images/favicon.webp"),
    )
    _BUNDLES = (Path("runtime.js"), Path("vendors~main.js"), Path("main.js"))

    @classmethod
    def create(
        cls,
        aws_region: str,
        bucket: str,
        base_key: str,
        tc_env: ToolchainEnv,
        deployer: Deployer,
        cluster: KubernetesCluster | None,
    ) -> BuildAndDeployToolchainSPA:
        return cls(
            aws_region=aws_region,
            bucket=bucket,
            base_key=base_key,
            tc_env=tc_env,
            deployer=deployer,
            cluster=cluster,
            app_name="spa",
            local_build_dir=Path("dist/spa"),
            js_src_dir=Path("src/node/toolchain/frontend/"),
            extra_files=cls.FAV_ICONS,
            backend_service="servicerouter",
            sentry_project_name="toolchain-frontend",
        )

    def get_bundle_names(self) -> tuple[Path, ...]:
        return self._BUNDLES


class BuildAndDeployPantsDemoSite(BuildAndDeployFrontendApp):
    # Might need to add more types down the line, for now including the .js files is enough.
    _BUNDLE_EXTS = frozenset([".js"])
    _EXTRA_RESOURCES = (Path("src/python/toolchain/pants_demos/depgraph/static/pants-demo-site/"),)

    @classmethod
    def create(
        cls,
        aws_region: str,
        bucket: str,
        base_key: str,
        tc_env: ToolchainEnv,
        deployer: Deployer,
        cluster: KubernetesCluster | None,
    ) -> BuildAndDeployPantsDemoSite:
        js_dir = Path("src/node/toolchain/pants-demo-site/")
        return cls(
            aws_region=aws_region,
            bucket=bucket,
            base_key=base_key,
            tc_env=tc_env,
            deployer=deployer,
            cluster=cluster,
            app_name="pants-demo-site",
            local_build_dir=js_dir / "build" / "static" / "js",
            js_src_dir=js_dir,
            extra_files=cls._EXTRA_RESOURCES,
            backend_service="pants-demos-depgraph-web",
            sentry_project_name="pants-demos-js",
        )

    def get_bundle_names(self) -> tuple[Path, ...]:
        asset_manifest = self.local_build_dir.parent.parent / "asset-manifest.json"
        manifest = json.loads(asset_manifest.read_bytes())
        files = (Path(name) for name in manifest["files"].values())
        return tuple(fl for fl in files if fl.suffix in self._BUNDLE_EXTS)
