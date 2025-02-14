# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

import httpx
from humanize.filesize import naturalsize

from toolchain.aws.secretsmanager import SecretsManager
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv

_logger = logging.getLogger(__name__)


class SentryApiClient:
    _BASE_URL = "https://sentry.io/api/0"
    _ORG_SLUG = "toolchain"

    @classmethod
    def for_devops(cls, aws_region: str, toolchain_env: ToolchainEnv, prod_project: str) -> SentryApiClient:
        secrets_mgr = SecretsManager(region=aws_region)
        project = "k8s-dev" if toolchain_env.is_dev else prod_project  # type: ignore[attr-defined]
        api_key_secret = secrets_mgr.get_secret("sentry-integration")
        if not api_key_secret:
            raise ToolchainAssertion("Failed to load Sentry API Key")
        api_key = json.loads(api_key_secret)["SENTRY_API_KEY"]
        return cls(api_key=api_key, organization_slug=cls._ORG_SLUG, project=project)

    def __init__(self, *, api_key: str, organization_slug: str, project) -> None:
        self._project = project
        self._client = httpx.Client(
            base_url=f"{self._BASE_URL}/organizations/{organization_slug}/",
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Toolchain-Integration",
            },
        )

    def get_release_or_none(self, *, release_name: str) -> dict | None:
        # https://docs.sentry.io/api/releases/list-an-organizations-releases/
        resp = self._client.get(url="releases/", params={"query": release_name})
        resp.raise_for_status()
        releases = resp.json()
        if len(releases) == 0:
            return None
        if len(releases) > 1:
            raise ToolchainAssertion(f"multiple replease with name: {release_name}: {len(releases)}")
        return releases[0]

    def create_release(self, *, project_slug: str, release_name: str, commit_sha: str) -> dict:
        # https://docs.sentry.io/api/releases/create-a-new-release-for-an-organization/
        release_info = {
            "version": release_name,
            "ref": commit_sha,
            "projects": [project_slug],
            "date_released": None,
            "date_started": utcnow().isoformat(),
        }
        resp = self._client.post(url="releases/", json=release_info)
        resp.raise_for_status()
        return resp.json()

    def update_release(self, *, project_slug: str, release_name: str) -> dict:
        # https://docs.sentry.io/api/releases/update-an-organizations-release/
        release_info = {"projects": [project_slug], "date_released": utcnow().isoformat()}
        resp = self._client.put(url=f"releases/{release_name}/", json=release_info)
        resp.raise_for_status()
        return resp.json()

    def upload_release_files(
        self,
        *,
        release_name: str,
        file_paths: Sequence[Path],
        base_local_dir: Path,
        base_version_path: str,
    ) -> list[dict]:
        # https://docs.sentry.io/api/releases/upload-a-new-organization-release-file/
        _logger.info(f"Uploading files: {[path.as_posix() for path in file_paths]}")
        responses_data = []
        for fl in file_paths:
            _logger.info(f"Uploading file {fl.as_posix()}  {naturalsize(fl.stat().st_size)}")
            # https://docs.sentry.io/platforms/javascript/guides/react/sourcemaps/troubleshooting_js/#using-the-
            name = f"~/{base_version_path}/{fl.relative_to(base_local_dir).as_posix()}"
            resp = self._client.post(
                url=f"releases/{release_name}/files/",
                files={"file": fl.open(mode="rb")},
                data={"name": name},
                timeout=300,
            )
            resp.raise_for_status()
            responses_data.append(resp.json())
        return responses_data

    def upload_js_release_files(
        self,
        *,
        release_name: str,
        commit_sha: str,
        release_files: Sequence[Path],
        base_local_dir: Path,
        base_version_path: str,
    ) -> None:
        if not release_files:
            raise ToolchainAssertion("No release files provided.")
        project = self._project
        if self.get_release_or_none(release_name=release_name):
            _logger.info(f"Files already uploaded for release: {release_name}")
            return

        _logger.info(
            f"Upload release files to Sentry Project {project}. {release_name=} files {len(release_files)} files"
        )
        try:
            self.create_release(project_slug=project, release_name=release_name, commit_sha=commit_sha)
            self.upload_release_files(
                release_name=release_name,
                file_paths=release_files,
                base_local_dir=base_local_dir,
                base_version_path=base_version_path,
            )
            self.update_release(project_slug=project, release_name=release_name)
        except httpx.HTTPStatusError as error:
            _logger.error(f"failed. {error!r} url={error.request.url} content={error.response.content.decode()}")
            raise
