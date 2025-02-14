# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from typing import Callable

from opensearchpy.helpers import bulk as opensarch_bulk

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.records.adapters import to_elasticsearch_document
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.util.elasticsearch.client_helper import get_open_search_client

_logger = logging.getLogger(__name__)


class RunInfoIndex:
    @classmethod
    def for_customer_id(cls, settings, customer_id: str):
        return cls(settings, customer_id)

    def __init__(self, settings, customer_id: str) -> None:
        self._env = settings.TOOLCHAIN_ENV.get_env_name()
        self._customer_id = customer_id
        es_cfg: BuildSenseElasticSearchConfig = settings.ELASTICSEARCH_CONFIG
        self._es_indices = es_cfg.indices_names[1:]
        _logger.info(f"Indexes: {self._es_indices}")
        self._es_doc_type = es_cfg.doc_type
        self._client = get_open_search_client(es_cfg)

    def _get_doc_id_from_parts(self, repo_id: str, user_api_id: str, run_id: str) -> str:
        return f"{self._env}:{self._customer_id}:{repo_id}:{user_api_id}:{run_id}"

    def _get_doc_id(self, run_info: RunInfo) -> str:
        return self._get_doc_id_from_parts(
            repo_id=run_info.repo_id, user_api_id=run_info.user_api_id, run_id=run_info.run_id
        )

    def _get_expand_callback(self, index_name) -> Callable:
        def _expand_action_callback(run_info: RunInfo) -> tuple[dict, dict]:
            # We can't use the default/builtin expand_action since it treats "version" reserved field and maps it to the action
            # instead of the document (we store the pants version there)
            # https://github.com/elastic/elasticsearch-py/blob/e275834941ea053c300e2c4bc494fccd5265f127/elasticsearch/helpers/actions.py#L76
            # It also copies the json doc, which is wasteful for our use case.
            run_info_json = to_elasticsearch_document(run_info)
            action = {"index": {"_id": self._get_doc_id(run_info), "_index": index_name, "_type": self._es_doc_type}}
            return action, run_info_json

        return _expand_action_callback

    def index_runs(self, run_infos: list[RunInfo]) -> bool:
        if not run_infos:
            raise ToolchainAssertion("Empty run_infos passed to index_runs")
        error_count = 0
        for index_name in self._es_indices:
            error_count += self._index_runs_to_index(index_name, run_infos=run_infos)
        return error_count == 0

    def _index_runs_to_index(self, index_name: str, run_infos: list[RunInfo]) -> int:
        result: tuple[int, list] = opensarch_bulk(  # type: ignore[assignment]
            client=self._client,
            actions=run_infos,
            stats_only=False,
            expand_action_callback=self._get_expand_callback(index_name),
        )
        success, errors = result
        _logger.debug(
            f"Indexed {len(run_infos)} runs into ES {index_name}. successes={success} error_count={len(errors)}"
        )
        if errors:
            _logger.warning(f"Errors indexing runs to ES: {errors!r}")
        return len(errors)
