#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

import httpx
import tomlkit
from packaging import version
from packaging.specifiers import SpecifierSet
from pkg_resources import Requirement

from toolchain.base.toolchain_binary import ToolchainBinary

_logger = logging.getLogger(__name__)


class UpgradePythonReqs(ToolchainBinary):
    description = "Upgrade python requirements"

    _PANTS_CFG = Path("pants.toml")
    _SKIP_TOOLS = frozenset(
        (
            "flake8",  # We can't use flake8 6.x since it doesn't support running under pythong 3.7 which we use with the TC pants plugin
        )
    )

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._reqs_files = [Path(fl) for fl in cmd_args.reqs]
        self._client = httpx.Client(base_url="https://pypi.org/pypi")

    def run(self) -> int:
        for req_file in self._reqs_files:
            _logger.info(f"Processing: {req_file.as_posix()}")
            self._process_reqs_file(req_file)
        self._upgrade_python_tools(self._PANTS_CFG)
        return 0

    def _process_reqs_file(self, req_file: Path) -> bool:
        lines = []
        upgrades = []
        for line in req_file.read_text().splitlines():
            new_req = self._maybe_get_upgraded_req(line)
            if not new_req:
                lines.append(line)
            else:
                lines.append(new_req)
                upgrades.append(new_req)
        if upgrades:
            _logger.info(f"{req_file.as_posix()} upgrades: {', '.join(upgrades)}")
            req_file.write_text("\n".join(lines))
        else:
            _logger.warning(f"No Upgrades for {req_file.as_posix()}")
        return bool(upgrades)

    def _maybe_get_upgraded_req(self, req_line: str) -> str | None:
        if req_line.strip().endswith("no-upgrade"):
            return None
        req = Requirement.parse(req_line)  # TODO: add try-except and just copy the line as is if we can't parse it.
        if not req.specs or req.specs[0][0] != "==":
            return None
        response = self._client.get(f"{req.project_name}/json")
        response.raise_for_status()
        current_version = version.parse(req.specs[0][-1])
        latest_version = version.parse(response.json()["info"]["version"])
        if current_version == latest_version:
            return None
        req.specifier = SpecifierSet(f"=={latest_version}")  # type: ignore[attr-defined]
        return str(req)

    def _upgrade_python_tools(self, pants_cfg: Path) -> bool:
        upgrades = []
        cfg = tomlkit.parse(pants_cfg.read_text())
        for scope, scope_cfg in cfg.items():
            if scope in self._SKIP_TOOLS:
                continue
            for opt, val in scope_cfg.items():
                if opt != "version":
                    continue
                new_req = self._maybe_get_upgraded_req(val)
                if not new_req:
                    continue
                scope_cfg[opt] = new_req
                upgrades.append(new_req)
        if upgrades:
            _logger.info(f"{pants_cfg.as_posix()} upgrades: {', '.join(upgrades)}")
            pants_cfg.write_text(tomlkit.dumps(cfg))
        else:
            _logger.warning(f"No Upgrades for {pants_cfg.as_posix()}")
        return bool(upgrades)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("reqs", nargs="+")


if __name__ == "__main__":
    UpgradePythonReqs.start()
