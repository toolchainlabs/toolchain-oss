#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from tempfile import mkdtemp

import httpx

from toolchain.base.contexttimer import Timer
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.pants_demos.depgraph.job.metrics import Metrics
from toolchain.pants_demos.depgraph.job.repo_pants_bootstrap import RepoPantsBootstrapper
from toolchain.util.pants.runner import PantsRunError, PantsRunner

_logger = logging.getLogger(__name__)


class PantsDepgraphDemoJob(ToolchainBinary):
    # Based on grepping the pants source for `(TargetFilesGenerator):`
    TARGET_GENERATORS = (
        r"[a-z]*_sources$",
        r"[a-z]*_tests$",
        r"^resources$",
        r"^files$",
        r"^python_test_utils$",
    )
    _TARGET_GENERATOR_EXPRESSION = re.compile("|".join(f".*{item}" for item in TARGET_GENERATORS))

    description = (
        "Clones a python repo from GitHub and bootstrap pants in it, then renders a dependency graph for all targets."
    )

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"PantsDemo start: {cmd_args=}")
        self.work_dir = Path(mkdtemp(prefix="repo"))
        self._repo = cmd_args.repo
        self._branch = cmd_args.branch
        self._signed_s3_url = cmd_args.s3_url
        if self._signed_s3_url:
            self._signed_s3_url_fields = json.loads(cmd_args.s3_url_fields)
        self._metrics = Metrics(push_gateway_url=cmd_args.push_gateway_url)
        if cmd_args.git_mode == "ssh":
            boostrapper = RepoPantsBootstrapper.for_github_ssh(
                repo=self._repo, branch=self._branch, local_repo_dir=self.work_dir
            )
        elif cmd_args.git_mode == "http":
            boostrapper = RepoPantsBootstrapper.for_github_http(
                repo=self._repo, branch=self._branch, local_repo_dir=self.work_dir
            )
        else:
            raise ToolchainAssertion(f"Invalid git mode: {cmd_args.git_mode}")
        self._bootstrapper = boostrapper

    def run(self) -> int:
        with Timer() as timer:
            data = self._process_repo()
            data["timing"] = {"processing": int(timer.elapsed)}
            self._store_result(data)
        self._metrics.report_metrics()
        _logger.info(f"PantsDemo: {self._repo} completed. took {timer.elapsed:.3f} seconds.")
        return 0

    def _get_avatar(self) -> str | None:
        try:
            response = httpx.get(f"https://api.github.com/repos/{self._repo}")
            response.raise_for_status()
        except httpx.RequestError as error:
            _logger.warning(f"failed to get repo {self._repo} info via API: {error!r}")
        return response.json()["owner"]["avatar_url"]

    def _process_repo(self) -> dict:
        if not self._bootstrapper.check_repo_accessability():
            _logger.warning(f"repo: {self._repo} not accessible.")
            return {
                "errors": {"stage": "check-access", "message": "can't access repo"},
                "metadata": {"version": "1"},
                "repo": {"full_name": self._repo},
            }
        with Timer() as timer, self._metrics.track_clone_latency():
            repo_info = self._bootstrapper.clone()
        _logger.info(f"PantsDemo: clone repo took: {timer.elapsed:.3f} seconds")
        avatar = self._get_avatar()
        data = {
            "repo": {
                "commit_sha": repo_info.commit_sha,
                "branch": repo_info.branch_name,
                "full_name": self._repo,
            },
        }
        if avatar:
            data["repo"]["avatar"] = avatar
        account, *_ = self._repo.lower().partition("/")
        pants_init_config = self._bootstrapper.add_pants_files(skip_files_check=account == "pantsbuild")
        if pants_init_config is None:
            data["errors"] = {"stage": "add_pants", "message": "Pants files already exist in the repo"}
            return data
        extra_env = {"TOOLCHAIN_PANTS_DEMOSITE_VERSION": pants_init_config.pants_version}
        self._bootstrapper.detect_and_delete_generated_reqs()
        runner = PantsRunner(
            self.work_dir, log_runs=True, pants_config_file=pants_init_config.config_file_name, extra_env=extra_env
        )
        _logger.info("Bootstrap pants")
        with self._metrics.track_pants_latency("bootstrap"):
            pants_version = runner.get_version()
        _logger.info(f"pants bootstrapped. version: {pants_version}")
        if pants_version != pants_init_config.pants_version:
            data["errors"] = {"stage": "version_check", "message": f"Unexpected pants version: {pants_version}"}
            return data
        data["metadata"] = {
            "version": "1",
            "pants_version": pants_version,
        }
        targets_list: list[dict] = []
        try:
            with self._metrics.track_pants_latency("tailor"):
                tailor_results = runner.tailor()
            if tailor_results:
                self._bootstrapper.add_language_specific_files(tailor_results, pants_init_config.pants_config)
                with self._metrics.track_pants_latency("peek"):
                    targets_list = runner.peek()
            else:
                _logger.warning("No output from pants tailor - no targets generated")
                data["errors"] = {"stage": "tailor", "message": "No targets created by pants tailor"}
        except PantsRunError as error:
            data["errors"] = error.as_dict()
        if targets_list:
            data["target_list"] = self._remove_target_generators(targets_list)  # type: ignore[assignment]
            filtered_count = len(targets_list) - len(data["target_list"])
            _logger.info(
                f"filtered out {filtered_count} generators out of {len(targets_list)} targets for repo {self._repo}"
            )
        return data

    def _remove_target_generators(self, all_targets: list[dict]) -> list[dict]:
        """Having the  both a target generator (e.g., src/python/pants/core:core) and a rollup (e.g.,
        src/python/pants/core) of all the files in the dir makes the graph bigger and noisier than it has to be.

        Target generators are probably not meaningful concepts to demosite visitors so this logic removes them. Alos
        omitts the target part of the address entirely, since it will not be meaningful to general users.
        """

        def is_generator(target: dict) -> bool:
            return bool(self._TARGET_GENERATOR_EXPRESSION.match(target["target_type"]))

        return [tgt for tgt in all_targets if not is_generator(tgt)]

    def _store_result(self, result: dict) -> None:
        result_data = json.dumps(result)
        if not self._signed_s3_url:
            _logger.info(f"result: {json.dumps(result, indent=4)}")
            return
        _logger.info(f"Write result to {self._signed_s3_url}, {len(result_data):,} bytes")
        response = httpx.post(
            url=self._signed_s3_url, data=self._signed_s3_url_fields, files={"file": result_data.encode()}
        )
        _logger.info(f"Upload response: status_code={response.status_code} {response.text}")
        response.raise_for_status()

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        parser.add_argument("--repo", required=True, type=str, help="Repo full name (account/repo).")
        parser.add_argument("--branch", type=str, help="Repo branch. If not set, defaults to active branch.")
        parser.add_argument("--s3-url", default=None, type=str, help="Presigned s3 url to upload the results file to.")
        parser.add_argument(
            "--s3-url-fields", default=None, type=str, help="json encoded fields to add to the result upload request"
        )
        parser.add_argument("--git-mode", default="ssh", choices=("ssh", "http"), type=str, help="clone mode.")
        parser.add_argument(
            "--push-gateway-url", type=str, default=None, help="URL to push gateway (for metrics reporting)."
        )


if __name__ == "__main__":
    PantsDepgraphDemoJob.start()
