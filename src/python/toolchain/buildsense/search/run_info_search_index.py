# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import operator
from collections.abc import Iterator
from dataclasses import dataclass
from functools import reduce
from typing import Any

from opensearch_dsl import A, Q, Search
from opensearch_dsl.response import Response
from opensearchpy import ConnectionError, TransportError

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainTransientError
from toolchain.buildsense.records.run_info import RunKey
from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.buildsense.types import FieldsMap, FieldValue
from toolchain.util.elasticsearch.client_helper import get_open_search_client

_logger = logging.getLogger(__name__)


class SearchTransientError(ToolchainTransientError):
    """Raised on transient ES errors."""

    def __init__(self, call_name: str, msg: str) -> None:
        self._call_name = call_name
        super().__init__(msg)

    @property
    def call_name(self) -> str:
        return self._call_name


@dataclass(frozen=True)
class ResultsPage:
    items: tuple[RunKey, ...]
    total_count: int

    @property
    def count(self) -> int:
        return len(self.items)


def _array_match(field: str, value: str | list[str]):
    values = [value] if isinstance(value, str) else value
    expression = reduce(operator.ior, (Q("match_phrase", **{field: val}) for val in values))
    if len(values) > 1:
        expression.minimum_should_match = 1
    return expression


def _field_exists(field: str, value: bool):
    base_expression = Q("exists", field=field)
    if value is True:
        return base_expression
    if value is False:
        return Q("bool", must_not=[base_expression])
    raise ToolchainAssertion(f"Invalid boolean value: {value}")


class RunInfoSearchIndex:
    _PAGE_SIZE_LIMIT = 50
    DEFAULT_PAGE_SIZE = 20
    _PR_VALUES_WINDOW = datetime.timedelta(days=30)
    _FIELD_MAP_TRANSFORM = {"goals": "computed_goals", "ci": "ci_info", "pr": "ci_info.pull_request"}
    _ALLOWED_QUERY_FIELDS = {
        "cmd_line": "match",
        "pr": "term",
        "outcome": "term",
        "user_api_id": "term",
        "branch": "match",
        "run_time": "range",
        "goals": _array_match,
        "ci": _field_exists,
        "title": "match",
    }
    _ALLOWED_SORT_OPTIONS = ["timestamp", "-timestamp", "run_time", "-run_time", "outcome", "-outcome"]
    AGGREGATIONS_MAP = {
        "outcome": "outcome",
        "version": "version.keyword",
        "branch": "branch.keyword",
        "user_api_id": "user_api_id",
        "goals": "computed_goals",
        "pr": "ci_info.pull_request",
        "title": "title",
    }
    ALLOWED_AGGREGATIONS = frozenset(AGGREGATIONS_MAP.keys())

    @classmethod
    def for_customer_id(cls, settings, customer_id: str, timeout_in_sec: int | None = None) -> RunInfoSearchIndex:
        return cls(settings, customer_id, timeout_in_sec=timeout_in_sec)

    def __init__(self, settings, customer_id: str, timeout_in_sec: int | None) -> None:
        self._env = settings.TOOLCHAIN_ENV.get_env_name()
        self._customer_id = customer_id
        es_cfg: BuildSenseElasticSearchConfig = settings.ELASTICSEARCH_CONFIG
        self._index_name = es_cfg.alias_name
        self._es_doc_type = es_cfg.doc_type
        self._client = get_open_search_client(es_cfg, timeout_in_sec=timeout_in_sec)

    def __str__(self) -> str:
        return f"RunInfoSearchIndex(environment={self._env} index={self._index_name} customer_id={self._customer_id})"

    def check_access(self) -> dict:
        domain = self._client.info()
        stats = self._client.indices.stats(index=self._index_name)
        return {"domain": domain, "stats": stats}

    def _get_search(self, repo_id: str | None = None) -> Search:
        search = Search(using=self._client, index=self._index_name)
        base_query = Q("term", server_info__environment=self._env) & Q("term", customer_id=self._customer_id)
        if repo_id:
            base_query = base_query & Q("term", repo_id=repo_id)
        search = search.query(base_query)
        return search

    def _hit_to_runkey(self, hit) -> RunKey:
        return RunKey(user_api_id=hit.user_api_id, repo_id=hit.repo_id, run_id=hit.run_id)

    def _execute_search(self, query, page_size: int, offset: int | None = None, sort=None) -> ResultsPage:
        if page_size > self._PAGE_SIZE_LIMIT:
            raise ToolchainAssertion(f"Max page size exceeded. Max: {self._PAGE_SIZE_LIMIT} got: {page_size}")
        extras = {"size": page_size}
        if offset:
            extras["from"] = offset

        sort = sort or "-timestamp"
        if sort not in self._ALLOWED_SORT_OPTIONS:
            raise ToolchainAssertion(f"Invalid sort option: {sort!r}.")
        query = query.sort(sort, "-server_info.accept_time", "_id")
        query = query.extra(**extras)
        result = self._execute(query, "search")
        run_keys = tuple(self._hit_to_runkey(hit) for hit in result.hits)
        return ResultsPage(items=run_keys, total_count=result.hits.total.value)

    def _execute(self, search: Search, call_name: str) -> Response:
        _logger.debug(f"ES {call_name}: {search.to_dict()}")
        try:
            return search.execute()
        except ConnectionError as error:
            _logger.warning(f"connection error on {call_name} {error!r} {search.to_dict()}")
            raise SearchTransientError(call_name, f"Connection error {error}") from error
        except TransportError as error:
            _logger.warning(f"TransportError error on {call_name} {error!r} {search.to_dict()}")
            if error.status_code == 429:
                raise SearchTransientError(call_name, f"TransportError error {error}") from error
            raise

    def get_for_run_id(self, repo_id: str, run_id: str) -> RunKey | None:
        if not repo_id or not run_id:
            raise ToolchainAssertion("Must provide a run_id & repo_id")
        search = self._get_search(repo_id).query("term", run_id=run_id)
        try:
            result = search.execute()
        except ConnectionError as error:
            _logger.warning(f"connection error on get_for_run_id {error!r} {search.to_dict()}")
            raise SearchTransientError("get_for_run_id", f"Connection error {error}") from error
        if not result.hits:
            _logger.warning(f"Could not find data for repo_id={repo_id} run_id={run_id}")
            return None
        return self._hit_to_runkey(result.hits[0])

    def _add_date_range(
        self, query: Search, earliest: datetime.datetime | None = None, latest: datetime.datetime | None = None
    ) -> Search:
        if not earliest and not latest:
            return query
        if earliest and latest and earliest > latest:
            raise ToolchainAssertion("Earliest date is after latest date.")
        ts_dict: dict[str, Any] = {"format": "epoch_second"}
        if earliest:
            ts_dict["gte"] = int(earliest.timestamp())
        if latest:
            ts_dict["lte"] = int(latest.timestamp())
        return query.query("range", timestamp=ts_dict)

    def _add_query_field(self, query: Search, field: str, value: FieldValue) -> Search:
        if field not in self._ALLOWED_QUERY_FIELDS:
            raise ToolchainAssertion(f"Queries not allowed for field: {field}.")
        search_type = self._ALLOWED_QUERY_FIELDS.get(field)
        # Allow different field names in API vs the field names in ES
        # For example, goals in the API is called computed_goals in ES.
        field = self._FIELD_MAP_TRANSFORM.get(field, field)

        if callable(search_type):
            return query.query(search_type(field, value))

        if search_type == "range":
            if not isinstance(value, tuple):
                raise ToolchainAssertion(f"must provide a range tuple for range query on: {field}")
            values_dict = {"gte": int(value[0].total_seconds() * 1000)} if value[0] else {}
            if value[1]:
                values_dict["lte"] = int(value[1].total_seconds() * 1000)
            if not values_dict:
                raise ToolchainAssertion("None values pair in range field.")
            value = values_dict  # type: ignore[assignment]
        elif not isinstance(value, (int, str)):
            raise ToolchainAssertion(f"List of values not supported with field: {field}")
        return query.query(search_type, **{field: value})

    def search_all_matching(
        self,
        *,
        repo_id: str,
        field_map: FieldsMap,
        page_size: int,
        earliest: datetime.datetime | None = None,
        latest: datetime.datetime | None = None,
        sort: str | None = None,
        offset: int | None = None,
    ) -> ResultsPage:
        search = self._get_search(repo_id)
        search = self._add_date_range(search, earliest=earliest, latest=latest)
        for field, value in sorted(field_map.items()):
            search = self._add_query_field(search, field, value)
        return self._execute_search(search, page_size=page_size, offset=offset, sort=sort)

    def repo_has_builds(self, repo_id: str) -> bool:
        search = self._get_search(repo_id).extra(size=0)
        result = self._execute(search, "has_builds")
        return result.hits.total.value > 0

    def get_possible_values(self, *, repo_id: str, field_names: tuple[str, ...]) -> dict[str, dict[str, list[str]]]:
        if not self.ALLOWED_AGGREGATIONS.issuperset(field_names):
            raise ToolchainAssertion(f"Not allowed to aggregate on {field_names}")
        search = self._get_search(repo_id)
        for field in field_names:
            search = self._add_field_agg(search, field)
        search = search.extra(size=0)
        aggregations = self._execute(search, "aggregations").aggregations
        results = {}
        for field in field_names:
            buckets = aggregations[field].buckets
            results[field] = {"values": [str(bucket["key"]) for bucket in buckets]}
        return results

    def _add_field_agg(self, search, field: str):
        if field == "goals":
            # we have some bad data from older pants version in computed goals. I need to clean it up.
            # util then make sure we get goals only from newer version pants.
            search = search.query("term", server_info__stats_version="3")
        elif field == "pr":
            search = self._add_date_range(search, earliest=utcnow() - self._PR_VALUES_WINDOW)
        search.aggs.bucket(field, A("terms", field=self.AGGREGATIONS_MAP[field]))
        return search

    def _get_suggestions(self, suggestions) -> Iterator[str]:
        for suggestion in suggestions:
            for option in suggestion.options:
                yield option.text

    def get_title_completion_values(self, *, repo_id: str, title_phrase: str):
        search = self._get_search(repo_id).extra(size=0, _source="title")
        search = search.suggest(
            "title_suggest", title_phrase, completion={"field": "title.completion", "skip_duplicates": True}
        )
        suggest_result = self._execute(search, "suggest").suggest
        return list(self._get_suggestions(suggest_result.title_suggest))
