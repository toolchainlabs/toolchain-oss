#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import glob
import logging
import os
import subprocess
from argparse import ArgumentParser, Namespace
from pathlib import Path

from twine.package import PackageFile
from twine.repository import TEST_WAREHOUSE, WAREHOUSE
from twine.settings import Settings
from twine.utils import check_status_code

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.prod.readme_client import ReadmeClient, ReadmePage

_logger = logging.getLogger(__name__)


class PublishToolchainPantsPlugin(ToolchainBinary):
    CHANGELOG_FILE = Path("src/python/toolchain/pants/CHANGELOG.md")
    PLUGIN_TARGET_PATH = "src/python/toolchain:toolchain-pants-plugin"
    DIST_GLOB = "dist/toolchain.pants.plugin*"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._region = cmd_args.aws_region
        self._real_pypi = cmd_args.real_pypi
        self._repo_url = WAREHOUSE if cmd_args.real_pypi else TEST_WAREHOUSE
        self._pypi_api_token = self.maybe_et_api_token_from_env("PyPi", cmd_args.pypi_api_token_env_variable)
        self._readme_api_token = self.maybe_et_api_token_from_env("Readme.com", cmd_args.readme_api_token_env_variable)

    def maybe_et_api_token_from_env(self, token_name: str, env_var_name: str | None) -> str | None:
        if not env_var_name:
            return None
        api_token = os.environ.get(env_var_name, "").strip()
        if not api_token:
            raise ToolchainAssertion(f"Failed to load {token_name} API token from: {env_var_name}")
        return api_token

    def _get_dist_files(self) -> list[Path]:
        # Wheels files first
        filenames = sorted(glob.glob(self.DIST_GLOB), key=lambda x: -1 if x.endswith(".whl") else 0)
        return [Path(fn) for fn in filenames]

    def _get_packages(self, twine_settings: Settings) -> list[PackageFile]:
        # Wheels files first
        dists = self._get_dist_files()
        return [PackageFile.from_filename(fn.as_posix(), twine_settings.comment) for fn in dists]

    def _upload_packages(self, repository, packages_to_upload: list[PackageFile]) -> list[str]:
        if any(repository.package_is_uploaded(package) for package in packages_to_upload):
            raise ToolchainAssertion("Some packages already exist in pypi")
        uploaded_packages = []
        for package in packages_to_upload:
            resp = repository.upload(package)
            if resp.is_redirect:
                location = resp.headers["location"]
                raise ToolchainAssertion(f"Redirected to {location}")
            check_status_code(resp, True)
            resp.raise_for_status()
            uploaded_packages.append(package)
        return repository.release_urls(uploaded_packages)

    def upload_dist(self, api_token: str | None) -> tuple[str, ...]:
        """Uploads the toolchain pants plugin to pypi.

        This is based on the logic in https://github.com/pypa/twine/blob/main/twine/commands/upload.py but trimmed down
        to suit our needs
        """
        twine_settings = Settings(repository_url=f"{self._repo_url}/legacy/", username="__token__", password=api_token)
        packages_to_upload = self._get_packages(twine_settings)
        repository = twine_settings.create_repository()
        release_urls = self._upload_packages(repository, packages_to_upload)
        return tuple(release_urls)

    def build_dist(self) -> None:
        cmd = (
            "./pants",
            "--no-dynamic-ui",
            "--concurrent",
            "package",
            self.PLUGIN_TARGET_PATH,
        )
        _logger.info(f"Package {self.PLUGIN_TARGET_PATH}")
        try:
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as error:
            error_msg = ((error.stderr or b"") + (error.stdout or b"")).decode()  # type: ignore
            _logger.exception(f"Execute pants failed: {' '.join(cmd)}: {error_msg}")
            raise

    def _get_changelog_page(self) -> ReadmePage:
        changelog_lines = self.CHANGELOG_FILE.read_text().splitlines()
        # remove the first two lines that contains the "changelog" title since we don't need that on the published version.
        changelog = "\n".join(changelog_lines[2:])
        return ReadmePage(
            slug="toolchain-pants-plugin-changelog",
            title="Toolchain Pants Plugin Changelog",
            category="changelogs",
            body=changelog,
        )

    def _clean_existing(self) -> None:
        for dist in self._get_dist_files():
            _logger.info(f"Delete {dist.as_posix()}")
            dist.unlink(missing_ok=False)

    def run(self) -> int:
        client = (
            ReadmeClient(self._readme_api_token)
            if self._readme_api_token
            else ReadmeClient.from_aws_secret(self._region)
        )
        self._clean_existing()
        changelog = self._get_changelog_page()
        client.ping()
        self.build_dist()
        self.upload_dist(api_token=self._pypi_api_token)
        if self._real_pypi:
            client.create_or_update_doc(changelog)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--real-pypi",
            default=False,
            required=False,
            action="store_true",
            help="Use real pypi (default to use test pypi).",
        )
        parser.add_argument(
            "--pypi-api-token-env-variable",
            default="",
            type=str,
            required=False,
            help="Name of environment variable where password is stored",
        )
        parser.add_argument(
            "--readme-api-token-env-variable",
            default="",
            type=str,
            required=False,
            help="Name of environment variable where password is stored",
        )


if __name__ == "__main__":
    PublishToolchainPantsPlugin.start()
