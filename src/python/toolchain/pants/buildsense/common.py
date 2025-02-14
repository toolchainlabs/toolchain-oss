# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

Artifacts = Dict[str, bytes]
WorkUnits = List[dict]
WorkUnitsMap = Dict[str, dict]


@dataclass
class RunTrackerBuildInfo:
    has_ended: bool
    build_stats: dict
    log_file: Path | None

    @property
    def run_id(self) -> str:
        return self.build_stats["run_info"]["id"]
