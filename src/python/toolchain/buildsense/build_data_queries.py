# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass

from django.conf import settings

from toolchain.buildsense.ingestion.run_info_raw_store import BuildFile, RunInfoRawStore
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.common import RUN_LOGS_ARTIFACTS_FILE_NAME
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.search.run_info_search_index import FieldsMap, RunInfoSearchIndex
from toolchain.django.site.models import Repo

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResultsPage:
    results: tuple[RunInfo, ...]
    count: int
    offset: int | None
    total_pages: int


class BuildsQueries:
    @classmethod
    def for_customer_id(cls, customer_id: str):
        return cls(customer_id)

    def __init__(self, customer_id: str):
        self._customer_id = customer_id
        self._search_index = RunInfoSearchIndex.for_customer_id(settings, customer_id=customer_id)
        self._table = RunInfoTable.for_customer_id(customer_id)

    @property
    def allowed_get_values_fields(self) -> frozenset[str]:
        """Returns a set of field names that we allow the client to request possible values for.

        Getting the possible values (buckets) is based on performing an aggergation query in Elasticsearch
        """
        return self._search_index.ALLOWED_AGGREGATIONS

    def search_all_matching(
        self,
        repo_id: str,
        field_map: FieldsMap,
        earliest: datetime.datetime | None = None,
        latest: datetime.datetime | None = None,
        page_size: int | None = None,
        sort: str | None = None,
        page: int | None = None,
    ) -> SearchResultsPage:
        page_size = page_size or self._search_index.DEFAULT_PAGE_SIZE
        offset = page * page_size if page and page > 1 else None
        search_result = self._search_index.search_all_matching(
            repo_id=repo_id,
            field_map=field_map,
            earliest=earliest,
            latest=latest,
            page_size=page_size,
            sort=sort,
            offset=offset,
        )
        keys = search_result.items
        runs = self._table.get_by_run_ids(run_keys=keys, repo_id=repo_id) if keys else []
        if keys and len(keys) != len(runs):
            _logger.warning(f"Elasticsearch/DynamoDB result mismatch. ES={len(keys)} DynamoDB={len(runs)}")

        return SearchResultsPage(
            results=runs,
            count=search_result.total_count,
            offset=offset,
            total_pages=int(search_result.total_count / page_size),
        )

    def repo_has_builds(self, *, repo_id: str) -> bool:
        return self._search_index.repo_has_builds(repo_id=repo_id)

    def get_values(self, *, repo_id: str, field_names: tuple[str, ...]) -> dict[str, dict[str, list[str]]]:
        return self._search_index.get_possible_values(repo_id=repo_id, field_names=field_names)

    def suggest_title_values(self, *, repo_id: str, query: str) -> list[str]:
        return self._search_index.get_title_completion_values(repo_id=repo_id, title_phrase=query)

    def get_build(self, repo_id: str, user_api_id: str | None, run_id: str) -> RunInfo | None:
        if not user_api_id:
            run_key = self._search_index.get_for_run_id(repo_id=repo_id, run_id=run_id)
            if not run_key:
                return None
            user_api_id = run_key.user_api_id
        return self._table.get_by_run_id(repo_id=repo_id, user_api_id=user_api_id, run_id=run_id)

    def get_build_raw_data(self, repo, user_api_id: str | None, run_id: str) -> dict | None:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        run_info = self.get_build(repo_id=repo.pk, user_api_id=user_api_id, run_id=run_id)
        if not run_info:
            return None
        return raw_store.get_build_data(run_info)

    def get_build_trace(self, repo: Repo, user_api_id: str | None, run_id: str) -> dict | None:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        run_info = self.get_build(repo_id=repo.pk, user_api_id=user_api_id, run_id=run_id)
        if not run_info:
            _logger.warning(f"Build repo={repo.slug} {run_id=} not found")
            return None
        trace_file = raw_store.get_named_data(run_info, name="zipkin_trace.json")
        if not trace_file:
            _logger.warning(f"get_build_trace - no trace data {run_id=}")
            return None
        return json.loads(trace_file.content)

    def get_build_options(self, repo: Repo, user_api_id: str | None, run_id: str) -> dict | None:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        run_info = self.get_build(repo_id=repo.pk, user_api_id=user_api_id, run_id=run_id)
        if not run_info:
            _logger.warning(f"Build repo={repo.slug} {run_id=} not found")
            return None
        build_data = raw_store.get_build_data(run_info)
        if not build_data:
            _logger.warning(f"get_build_options - no build_data {run_id=}")
            return None
        options = build_data.get("recorded_options")
        if not options:
            _logger.warning(f"get_build_options - missing recorded_options {run_id=}")
            return None
        return options

    def _get_work_units(self, repo: Repo, run_info: RunInfo) -> dict:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        work_units_file = raw_store.get_work_units_artifacts(run_info)
        if not work_units_file:
            return {}
        return json.loads(work_units_file.content)

    def _convert_wu(self, wu: dict) -> dict:
        converted = {"name": wu["artifacts"], "description": wu["description"], "group": wu["name"]}
        content_types = wu.get("content_types")
        if content_types:
            converted["content_types"] = content_types
        if "result" in wu:
            converted["result"] = wu["result"]
        if "run_time_msec" in wu:
            converted["run_time_msec"] = wu["run_time_msec"]
        return converted

    def get_platform_info(self, repo: Repo, run_info: RunInfo) -> dict | None:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        platform_info_file = raw_store.get_platform_info(run_info)
        return json.loads(platform_info_file.content) if platform_info_file else None

    def get_build_artifacts(self, repo: Repo, run_info: RunInfo) -> dict:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        work_units_file = raw_store.get_work_units_artifacts(run_info)
        if not work_units_file:
            return {}
        wu_artifacts = json.loads(work_units_file.content)

        artifacts_by_goal = {}
        for goal, work_units in wu_artifacts.items():
            is_work_unit_goal = "work_unit_id" in work_units[0]
            artifact = {
                "type": "goal" if is_work_unit_goal else "run",
                "artifacts": [self._convert_wu(wu) for wu in work_units],
            }
            if not is_work_unit_goal and "_" in work_units[0]["name"]:
                artifact["name"] = work_units[0]["description"]
            artifacts_by_goal[goal] = artifact
        return artifacts_by_goal

    def get_build_artifact(self, repo: Repo, user_api_id: str, run_id: str, name: str) -> BuildFile | None:
        raw_store = RunInfoRawStore.for_repo(repo=repo)
        run_info = self.get_build(repo.pk, user_api_id, run_id)
        if not run_info:
            _logger.warning(f"Build repo={repo.slug} {run_id=} not found")
            return None
        data = raw_store.get_named_data(run_info, name=name)
        if data and name == RUN_LOGS_ARTIFACTS_FILE_NAME:
            # wrap log content for UI
            data.content = json.dumps(
                [
                    {
                        "name": "Pants run log",
                        "content_type": "text/log",
                        "content": data.content.decode(),
                    }
                ]
            ).encode()
        return data
