# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from pathlib import PurePath

from dateutil.parser import parse
from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.oss_metrics.records import (
    ReferralPath,
    ReferralSource,
    RepoDailyView,
    RepoInfoStats,
    RepoReferralPaths,
    RepoReferralSources,
    RepoViews,
)

_logger = logging.getLogger(__name__)


class GithubStatsRawStore:
    @classmethod
    def from_customer_and_repo_id(cls, customer_id: str, repo_id: str) -> GithubStatsRawStore:
        path = PurePath(settings.GITHUB_REPO_STATS_BASE_KEY) / customer_id / repo_id
        return cls(bucket=settings.SCM_INTEGRATION_BUCKET, s3_path=path)

    def __init__(self, bucket: str, s3_path: PurePath) -> None:
        self._bucket = bucket
        self._s3_path = s3_path

    def _get_raw_data(self, day: datetime.date, data_name: str) -> tuple[dict | list | None, PurePath | None]:
        key_prefix = self._s3_path / day.isoformat()
        s3 = S3()
        for key in s3.keys_with_prefix(bucket=self._bucket, key_prefix=key_prefix.as_posix()):
            path = PurePath(key)
            if path.stem != data_name:
                continue
            return json.loads(s3.get_content(bucket=self._bucket, key=key)), path
        return None, None

    def load_repo_info_stats(cls, raw_data: dict) -> RepoInfoStats:
        stats = {fn: raw_data[f"{fn}_count"] for fn in RepoInfoStats.get_stat_fields()}
        return RepoInfoStats(timestamp=parse(raw_data["updated_at"]), **stats)

    def load_referral_sources(cls, key: PurePath, raw_data: list) -> RepoReferralSources:
        return RepoReferralSources(
            timestamp=parse(key.parent.name), referrers=tuple(ReferralSource(**src) for src in raw_data)
        )

    def load_referral_paths(cls, key: PurePath, raw_data: list) -> RepoReferralPaths:
        return RepoReferralPaths(
            timestamp=parse(key.parent.name), referrers=tuple(ReferralPath(**rp) for rp in raw_data)
        )

    def load_repo_views(cls, key: PurePath, raw_data: dict) -> RepoDailyView:
        def to_view(row):
            return RepoViews(timestamp=parse(row["timestamp"]), count=row["count"], uniques=row["uniques"])

        return RepoDailyView(
            day=parse(key.parent.name).date(),
            count=raw_data["count"],
            uniques=raw_data["uniques"],
            views=tuple(to_view(vw) for vw in raw_data["views"]),
        )

    def get_repo_stats(self, day: datetime.date) -> RepoInfoStats | None:
        data, _ = self._get_raw_data(day, "repo_info")
        return self.load_repo_info_stats(data) if data else None  # type: ignore[arg-type]

    def get_referral_sources(self, day: datetime.date) -> RepoReferralSources | None:
        data, key = self._get_raw_data(day, "repo_referral_sources")
        return self.load_referral_sources(key, data) if data and key else None  # type: ignore[arg-type]

    def get_views(self, day: datetime.date) -> RepoDailyView | None:
        data, key = self._get_raw_data(day, "repo_views")
        return self.load_repo_views(key, data) if data and key else None  # type: ignore[arg-type]

    def get_referral_paths(self, day: datetime.date) -> RepoReferralPaths | None:
        data, key = self._get_raw_data(day, "repo_referral_paths")
        return self.load_referral_paths(key, data) if data and key else None  # type: ignore[arg-type]
