# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from toolchain.base.contexttimer import Timer
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError

_logger = logging.getLogger(__name__)


class PantsRunError(ToolchainError):
    def __init__(self, goal: str, message: str) -> None:
        super().__init__(message)
        self._goal = goal

    def as_dict(self) -> dict[str, str]:
        return {"stage": self._goal, "message": f"Pants {self._goal} failed", "details": str(self)}


class PantsRunner:
    _BUILD_FILE_CREATION = re.compile(r"(?:Created|Updated) (?P<build_file>[\w_/]+BUILD):")
    _TARGET_CREATION = re.compile(r"\s*- Added (?P<target_type>[a-z_]+) target (?P<name>[:\w\/]*)")

    def __init__(
        self,
        work_dir: Path | None = None,
        pants_config_file: str | None = None,
        log_runs: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self._work_dir = work_dir
        self._pants_script_path = "./pants"
        self._options = ("--no-dynamic-ui",)
        self._log_runs = log_runs
        self._pants_config_file = pants_config_file or "pants.toml"
        self._extra_env = extra_env or {}

    def get_dependencies(self, target: str, third_party_filter: str | None = None) -> list[str]:
        results_file_data = self.run_with_results_file(
            "dependencies", target, "dependencies-output-file", "--dependencies-sep=,", "--dependencies-transitive"
        )

        def should_filter_dep(dependency: str) -> bool:
            # Get rid of 3rd party dependencies also strip the target name from relevant targets.
            if not dependency:
                return True
            return bool(third_party_filter and dependency.startswith(third_party_filter))

        return sorted(dep.split(":")[0] for dep in results_file_data.split(",") if not should_filter_dep(dep))

    def peek(self, target: str = "::") -> list[dict]:
        results_file_data = self.run_with_results_file("peek", target, "peek-output-file")
        return json.loads(results_file_data)

    def get_version(self) -> str:
        return self.run_pants_cmd(goal="version", cmd_args=["--version"]).strip()

    def _get_build_file(self, line: str) -> str:
        match = self._BUILD_FILE_CREATION.match(line)
        if not match:
            raise ToolchainAssertion(f"Can't find build file name in: {line}")
        return match.groupdict()["build_file"]

    def tailor(self, target: str = "::") -> str:
        return self.run_pants("tailor", target).strip()

    def get_targets(self, target_type: str) -> tuple[str, ...]:
        results_file_data = self.run_with_results_file(
            "filter",
            "::",
            "filter-output-file",
            f"--filter-target-type={target_type}",
            "--filpter-sep=','",
        )
        return tuple(tgt.strip("'") for tgt in results_file_data.split(",") if tgt.strip("'"))

    def run_with_results_file(self, goal: str, target: str, file_name_arg: str, *goal_options: str) -> str:
        with tempfile.NamedTemporaryFile() as tf:
            self.run_pants(goal, target, f"--{file_name_arg}={tf.name}", *goal_options)
            return tf.read().decode()

    def run_pants(self, goal: str, target: str, *goal_options: str) -> str:
        cmd_args = [goal]
        cmd_args.extend(goal_options)
        cmd_args.append(target)
        return self.run_pants_cmd(goal, cmd_args)

    def run_pants_cmd(self, goal: str, cmd_args: list[str]) -> str:
        cmd = [self._pants_script_path]
        proc_env = os.environ.copy()
        proc_env.update(  # Setting a single config file since we don't want to allow multiple config files
            {
                "PANTS_TOML": self._pants_config_file,  # used by the pants script to read pants version from the config file.
                "PANTS_CONFIG_FILES": f"['{self._pants_config_file}']",  # used by pants itself.
            }
        )
        proc_env.update(self._extra_env)
        cmd.extend(self._options)
        cmd.extend(cmd_args)
        with Timer() as timer:
            result = subprocess.run(cmd, cwd=self._work_dir, capture_output=True, check=False, env=proc_env)
            if result.returncode != 0:
                error_msg = ((result.stderr or b"") + (result.stdout or b"")).decode()  # type: ignore
                _logger.exception(f"Execute pants failed: {' '.join(cmd)}: {error_msg}")
                raise PantsRunError(goal=goal, message=error_msg)
        if self._log_runs:
            _logger.info(f"pants {goal}: took {timer.elapsed:.3f} seconds.")
        return result.stdout.decode()
