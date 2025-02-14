# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CIChecksResults:
    ci_type: str
    build_key: str
    pull_request_number: str
    job_link: str
