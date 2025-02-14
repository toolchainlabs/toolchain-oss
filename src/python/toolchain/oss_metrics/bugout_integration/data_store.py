# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from pathlib import PurePath

from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.oss_metrics.records import Telemetry

_logger = logging.getLogger(__name__)


class BugoutDataStore:
    # the date the anonymous telemetry feature was added to pants (the PR was submitted) https://github.com/pantsbuild/pants/pull/11697
    # There will not be data prior to this date.
    EARLIEST_DATE = datetime.date(2021, 3, 14)
    _KNOWN_TAGS = ("outcome", "pants_version", "python_implementation", "python_version", "platform", "os", "arch")

    @classmethod
    def from_django_settings(cls) -> BugoutDataStore:
        return cls(bucket=settings.BUGOUT_INTEGRATION_BUCKET, s3_path=PurePath(settings.BUGOUT_STORE_BASE_KEY))

    def __init__(self, bucket: str, s3_path: PurePath) -> None:
        self._bucket = bucket
        self._s3_path = s3_path

    def get_latest_data_date(self, journal_id) -> datetime.date:
        s3 = S3()
        dates_from_latest_year: set[datetime.date] = set()
        latest_year = 0
        for key in s3.keys_with_prefix(bucket=self._bucket, key_prefix=(self._s3_path / journal_id).as_posix()):
            key_path = PurePath(key)
            year = int(key_path.parent.name)
            if year < latest_year:
                continue
            key_date = datetime.date.fromisoformat(key_path.stem)
            if year > latest_year:
                dates_from_latest_year = set()
                latest_year = year
            dates_from_latest_year.add(key_date)
        if latest_year == 0:
            return self.EARLIEST_DATE
        return max(dates_from_latest_year)

    def _get_key(self, journal_id: str, day: datetime.date) -> PurePath:
        return self._s3_path / journal_id / str(day.year) / f"{day.isoformat()}.json"

    @classmethod
    def create_telemetry(cls, bugout_data: dict) -> Telemetry:
        content = json.loads(bugout_data["content"])
        all_tags = dict(tuple(tag_line.split(":")) for tag_line in bugout_data["tags"])  # type: ignore[arg-type]
        all_tags.update(content)
        tags = {tag: all_tags[tag] for tag in cls._KNOWN_TAGS}
        if tags.get("outcome", "").lower() == "none":
            del tags["outcome"]
        duration_str = content["duration"].lower()
        return Telemetry(
            timestamp=datetime.datetime.fromtimestamp(float(content["timestamp"]), tz=datetime.timezone.utc),
            run_id=content["run_id"],
            machine_id=content["machine_id"],
            user_id=content["user_id"],
            repo_id=content["repo_id"],
            tags=tags,
            duration=float(duration_str) if duration_str and duration_str != "none" else None,
            num_goals=int(content["num_goals"]),
            standard_goals=content["standard_goals"],
        )

    def save_data_for_day(self, *, journal_id: str, day: datetime.date, bugout_data: list[dict]) -> bool:
        if not bugout_data:
            raise ToolchainAssertion(f"No data/empty data for {day}")
        s3 = S3()
        key = self._get_key(journal_id, day)
        _logger.info(f"save_data_for_day {day=} {key=} entries={len(bugout_data)}")
        s3.upload_json_str(bucket=self._bucket, key=key.as_posix(), json_str=json.dumps(bugout_data))
        return True

    def get_data_for_day(self, journal_id: str, day: datetime.date) -> tuple[Telemetry, ...] | None:
        key = self._get_key(journal_id, day)
        s3 = S3()
        content = s3.get_content_or_none(self._bucket, key=key.as_posix())
        if not content:
            return None
        return tuple(self.create_telemetry(dp) for dp in json.loads(content))
