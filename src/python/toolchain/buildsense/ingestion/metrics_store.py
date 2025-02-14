# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from typing import Callable

from django.conf import settings
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
from urllib3.exceptions import HTTPError

from toolchain.base.toolchain_error import ToolchainTransientError
from toolchain.buildsense.ingestion.run_info_raw_store import BuildFile
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.types import FieldsMap, FieldValue
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.util.influxdb.client import InfluxDBConnectionConfig, get_client
from toolchain.util.influxdb.exceptions import MissingBucketError, is_missing_bucket_error
from toolchain.util.influxdb.manager import MetricsStoreManager

_logger = logging.getLogger(__name__)


class MetricsStoreTransientError(ToolchainTransientError):
    """Raised on transient InfluxDB errors."""

    def __init__(self, call_name: str, msg: str) -> None:
        self._call_name = call_name
        super().__init__(msg)

    @property
    def call_name(self) -> str:
        return self._call_name


class PantsMetricsStoreManager:
    @classmethod
    def for_repo(cls, repo: Repo) -> MetricsStoreManager:
        bucket_name = _get_bucket_name(repo)
        return MetricsStoreManager(config=settings.INFLUXDB_CONFIG, bucket_name=bucket_name)


class PantsMetricsStore:
    _WORK_UNIT_MEASUREMENT = "workunits"
    _INDICATORS_MEASUREMENT = "indicators"
    _FILTERS_VALUES_MAP: dict[str, Callable[[FieldValue], str]] = {
        "user_api_id": str,
        "outcome": str,
        "goals": lambda vl: ",".join(sorted(vl)),  # type: ignore[arg-type]
        "ci": lambda vl: "1" if vl else "0",
        "branch": str,
        "pr": str,
        "title": str,
    }

    @classmethod
    def for_repo(cls, repo: Repo) -> PantsMetricsStore:
        return cls(config=settings.INFLUXDB_CONFIG, repo=repo)

    @classmethod
    def check_access(cls) -> bool:
        client = get_client(settings.INFLUXDB_CONFIG)
        return client.ping()

    def __init__(self, config: InfluxDBConnectionConfig, repo: Repo) -> None:
        self._repo = repo
        self._influxdb_org_id = config.org_id
        self._client = get_client(config)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._bucket_name = _get_bucket_name(self._repo)

    def _get_context(self, run_info: RunInfo) -> str:
        if run_info.ci_info:
            return f"ci_{run_info.ci_info.run_type.value}"
        if "[docker]" in run_info.machine:
            return "docker"
        return "desktop"

    def _get_tags(self, run_info: RunInfo, user: ToolchainUser) -> dict[str, str]:
        tags = {
            "outcome": run_info.outcome,
            "pants_version": run_info.version,
            "goals": ",".join(sorted(run_info.computed_goals)),
            "ci": "1" if run_info.ci_info else "0",
            "context": self._get_context(run_info),
            "username": user.username,
            "user_api_id": user.api_id,
        }
        if run_info.branch:
            tags["branch"] = run_info.branch
        ci_info = run_info.ci_info
        if ci_info and ci_info.pull_request:
            tags["pr"] = ci_info.pull_request
        if ci_info and run_info.title:
            tags["title"] = run_info.title
        return tags

    def store_metrics(self, *, run_info: RunInfo, user: ToolchainUser, metrics_file: BuildFile | None) -> None:
        points = []
        if metrics_file:
            metrics = json.loads(metrics_file.content)[0]["content"]
            points.append(self.create_point(run_info, self._WORK_UNIT_MEASUREMENT, metrics))
        if run_info.indicators:
            points.append(self.create_point(run_info, self._INDICATORS_MEASUREMENT, run_info.indicators))
        if not points:
            return
        tags = self._get_tags(run_info, user)
        for point in points:
            self._add_tags(point, tags)
        points_names = ", ".join(point._name for point in points)
        _logger.info(f"store_metrics run_id={run_info.run_id} points={points_names}")
        try:
            self._write_api.write(bucket=self._bucket_name, record=points)
        except HTTPError as error:  # urllib3 network errors subclass HTTPError
            raise MetricsStoreTransientError(
                call_name="store_pants_metrics", msg=f"Network error storing metrics: {error!r}"
            )
        except ApiException as error:
            if is_missing_bucket_error(error):
                raise MissingBucketError.from_api_error(error)
            if error.status < 500:
                raise
            raise MetricsStoreTransientError(
                call_name="store_pants_metrics", msg=f"HTTP error storing metrics: {error!r}"
            )

    def _add_tags(self, point: Point, tags: dict[str, str]) -> None:
        for key, value in tags.items():
            point.tag(key, value)

    def create_point(self, run_info: RunInfo, measurement_name: str, data: dict) -> Point:
        point = Point.measurement(measurement_name).time(run_info.timestamp)
        for name, value in data.items():
            point.field(name, value)
        return point

    def _build_query(
        self,
        measurement: str,
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime | None,
        fields_regex: str,
        aggregation: str,
        additional_filters: dict[str, str],
    ) -> str:
        end_dt = f"{end_datetime.replace(tzinfo=None).isoformat()}Z" if end_datetime else "now()"
        start_dt = start_datetime.replace(tzinfo=None).isoformat()
        filter_rows = [
            f'|> filter(fn: (r) => r["{field}"] == "{value}")' for field, value in additional_filters.items()
        ]
        query_lines = [
            f'from(bucket: "{self._bucket_name}")',
            f"|> range(start:{start_dt}Z, stop:{end_dt})",
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement}" and r["_field"] =~ /{fields_regex}/)',
            *filter_rows,
            '|> group(columns: ["_measurement", "_field"], mode:"by")',
            f'|> {aggregation}(column: "_value")',
        ]
        return "\n".join(query_lines)

    def query_data(self, query: str):
        api = self._client.query_api()
        try:
            return api.query(query=query, org=self._influxdb_org_id)
        except ApiException as error:
            if not is_missing_bucket_error(error):
                raise
            raise MissingBucketError.from_api_error(error)

    def query_sums(
        self,
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime | None,
        filters: dict[str, str],
    ) -> dict[str, float]:
        query = self._build_query(
            self._INDICATORS_MEASUREMENT,
            start_datetime,
            end_datetime,
            fields_regex="saved_cpu_time.?|hits|total",
            aggregation="sum",
            additional_filters=filters,
        )
        res = self.query_data(query)
        return self._tables_to_dict(res)

    def query_hit_fractions(
        self,
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime | None,
        filters: dict[str, str],
    ) -> dict[str, float]:
        query = self._build_query(
            self._INDICATORS_MEASUREMENT,
            start_datetime,
            end_datetime,
            fields_regex="hit_fraction.?",
            aggregation="mean",
            additional_filters=filters,
        )
        res = self.query_data(query)
        return self._tables_to_dict(res)

    def _to_filters(self, field_map: FieldsMap) -> dict[str, str]:
        filters: dict[str, str] = {}
        for field, value in sorted(field_map.items()):
            func = self._FILTERS_VALUES_MAP.get(field)
            if func:
                filters[field] = func(value)
        return filters

    def get_aggregated_indicators(
        self,
        earliest: datetime.datetime,
        latest: datetime.datetime | None,
        fields_map: FieldsMap,
    ) -> dict[str, float]:
        # TODO : gracefully handle missing bucket error (404)
        filters = self._to_filters(fields_map)
        result = self.query_hit_fractions(start_datetime=earliest, end_datetime=latest, filters=filters)
        result.update(self.query_sums(start_datetime=earliest, end_datetime=latest, filters=filters))
        return result

    def _tables_to_dict(self, tables) -> dict[str, float]:
        return {table.records[0].get_field(): table.records[0].get_value() for table in tables}


def _get_bucket_name(repo: Repo) -> str:
    # For now we use slugs, this makes the data easier to handle in native tools (built in InfluxDB UI and grafana)
    # However, this is not robust since slugs can change, so in the future, we will need to use repo.id for bucket name.
    return f"{repo.customer.slug}/{repo.slug}"
