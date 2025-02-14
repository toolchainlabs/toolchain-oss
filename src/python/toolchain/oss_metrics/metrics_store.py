# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections.abc import Sequence

from django.conf import settings
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from toolchain.base.contexttimer import Timer
from toolchain.oss_metrics.records import (
    RepoDailyView,
    RepoInfoStats,
    RepoReferralPaths,
    RepoReferralSources,
    Telemetry,
)
from toolchain.util.influxdb.client import InfluxDBConnectionConfig, get_client
from toolchain.util.influxdb.manager import MetricsStoreManager

_logger = logging.getLogger(__name__)


_USAGE_TELEMETRY_BUCKET = "anonymous-telemetry"
_REPO_METRICS = "repo-metrics"


class AnonymousTelemetryMetricStoreManager:
    _BUCKETS = (_USAGE_TELEMETRY_BUCKET, _REPO_METRICS)

    @classmethod
    def init_buckets(cls, recreate: bool) -> None:
        for bucket in cls._BUCKETS:
            msm = MetricsStoreManager(config=settings.INFLUXDB_CONFIG, bucket_name=bucket)
            msm.init_bucket(recreate=recreate)


class AnonymousTelemetryMetricStore:
    _REQUEST_TIMEOUT = datetime.timedelta(seconds=90)  # We write large batches here so allow for longer timeouts.

    @classmethod
    def create(cls) -> AnonymousTelemetryMetricStore:
        return cls(config=settings.INFLUXDB_CONFIG, bucket=_USAGE_TELEMETRY_BUCKET)

    def __init__(self, config: InfluxDBConnectionConfig, bucket: str) -> None:
        self._influxdb_org_id = config.org_id
        self._client = get_client(config, request_timeout=self._REQUEST_TIMEOUT)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._bucket_name = bucket

    def _create_point(self, measurement_name, telemetry: Telemetry) -> Point:
        point = Point.measurement(measurement_name).time(telemetry.timestamp)
        for name, value in telemetry.tags.items():
            point.field(name, value)
        return point

    def _duration_point(self, telemetry: Telemetry) -> Point:
        pnt = self._create_point("duration", telemetry)
        pnt.field("val", telemetry.duration)
        return pnt

    def _num_goals_point(self, telemetry: Telemetry) -> Point:
        pnt = self._create_point("num_goals", telemetry)
        pnt.field("val", telemetry.num_goals)
        return pnt

    def _repo_and_user_point(self, telemetry: Telemetry) -> Point:
        point = Point.measurement("uniques").time(telemetry.timestamp)
        point.field("repo", telemetry.repo_id)
        point.field("user", telemetry.user_id)
        return point

    def store_telemetry(self, telemetry_points: Sequence[Telemetry]):
        points = [self._duration_point(tm) for tm in telemetry_points if tm.duration is not None]
        points.extend(self._num_goals_point(tm) for tm in telemetry_points)
        points.extend(self._repo_and_user_point(tm) for tm in telemetry_points)
        with Timer() as timer:
            self._write_api.write(bucket=self._bucket_name, record=points)
        _logger.info(f"store_telemetry: rows={len(points)} for {len(telemetry_points)} time_took={timer.elapsed}")


class RepoStatsMetricStore:
    @classmethod
    def create(cls) -> RepoStatsMetricStore:
        return cls(config=settings.INFLUXDB_CONFIG, bucket=_REPO_METRICS)

    def __init__(self, config: InfluxDBConnectionConfig, bucket: str) -> None:
        self._influxdb_org_id = config.org_id
        self._client = get_client(config)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._bucket_name = bucket

    def _write(self, api_name: str, timestamp: datetime.datetime | datetime.date, points: list[Point]):
        with Timer() as timer:
            self._write_api.write(bucket=self._bucket_name, record=points)
        _logger.info(f"{api_name}: rows={len(points)} for stat day: {timestamp.isoformat()} time_took={timer.elapsed}")

    def _create_stats_point(self, measurement_name, stat: RepoInfoStats) -> Point:
        point = Point.measurement(measurement_name).time(stat.timestamp)
        point.field("val", stat.get_value(measurement_name))
        return point

    def _create_point(self, measurement_name, timestamp: datetime.datetime, val: int, **tags) -> Point:
        point = Point.measurement(measurement_name).time(timestamp)
        point.field("val", val)
        for name, value in tags.items():
            point.field(name, value)
        return point

    def store_info_stats(self, stat: RepoInfoStats):
        points = [self._create_stats_point(fn, stat) for fn in stat.get_stat_fields()]
        self._write("store_repo_info_stats", stat.timestamp, points)

    def store_views(self, views: RepoDailyView) -> None:
        points: list[Point] = []
        for view in views.views:
            points.extend(
                (
                    self._create_point("view_count", view.timestamp, view.count),
                    self._create_point("view_uniques", view.timestamp, view.uniques),
                )
            )
        self._write("store_views", views.day, points)

    def store_referral_sources(self, ref_sources: RepoReferralSources) -> None:
        points: list[Point] = []
        for ref_src in ref_sources.referrers:
            points.extend(
                (
                    self._create_point(
                        "referral_source_count", ref_sources.timestamp, ref_src.count, referrer=ref_src.referrer
                    ),
                    self._create_point(
                        "referral_source_uniques", ref_sources.timestamp, ref_src.uniques, referrer=ref_src.referrer
                    ),
                )
            )
        self._write("store_referral_sources", ref_sources.timestamp, points)

    def store_referral_paths(self, ref_paths: RepoReferralPaths) -> None:
        points: list[Point] = []
        for ref_path in ref_paths.referrers:
            points.extend(
                (
                    self._create_point(
                        "referral_source_count", ref_paths.timestamp, ref_path.count, path=ref_path.path
                    ),
                    self._create_point(
                        "referral_source_uniques", ref_paths.timestamp, ref_path.uniques, path=ref_path.path
                    ),
                )
            )
        self._write("store_referral_paths", ref_paths.timestamp, points)
