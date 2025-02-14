# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from dataclasses import dataclass, fields


@dataclass
class Telemetry:
    timestamp: datetime.datetime
    tags: dict[str, str]
    run_id: str
    user_id: str
    machine_id: str
    repo_id: str
    standard_goals: list[str]
    duration: float | None
    num_goals: int


@dataclass
class RepoInfoStats:
    timestamp: datetime.datetime
    open_issues: int
    forks: int
    watchers: int
    stargazers: int
    subscribers: int
    network: int

    @classmethod
    def get_stat_fields(cls) -> tuple[str, ...]:
        return tuple(field.name for field in fields(cls) if field.type == "int")

    def get_value(self, name: str) -> int:
        return getattr(self, name)


@dataclass
class ReferralSource:
    referrer: str
    count: int
    uniques: int


@dataclass
class RepoReferralSources:
    timestamp: datetime.datetime
    referrers: tuple[ReferralSource, ...]


@dataclass
class RepoViews:
    timestamp: datetime.datetime
    count: int
    uniques: int


@dataclass
class RepoDailyView:
    day: datetime.date
    views: tuple[RepoViews, ...]
    count: int
    uniques: int


@dataclass
class ReferralPath:
    path: str
    title: str
    count: int
    uniques: int


@dataclass
class RepoReferralPaths:
    timestamp: datetime.datetime
    referrers: tuple[ReferralPath, ...]
