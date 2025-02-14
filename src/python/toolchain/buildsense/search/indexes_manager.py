# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging

import pkg_resources

from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.util.elasticsearch.client_helper import get_open_search_client

_logger = logging.getLogger(__name__)


class BuildsenseIndexManager:
    @classmethod
    def for_django_settings(cls, settings) -> BuildsenseIndexManager:
        return cls(es_cfg=settings.ELASTICSEARCH_CONFIG)

    def __init__(self, es_cfg: BuildSenseElasticSearchConfig) -> None:
        self._cfg = es_cfg
        self._doc_type = es_cfg.doc_type
        self._client = get_open_search_client(es_cfg)

    def create_index(self) -> bool:
        new_index = self._cfg.new_index
        current_index = self._cfg.existing_index
        if not new_index:
            created = self._create_index_if_not_exists(current_index)
            if created:
                self._create_or_update_alias(alias_name=self._cfg.alias_name, index_name=current_index)
            return created
        created = self._create_index_if_not_exists(new_index)
        if created:
            self._reindex(current_index, new_index)
        return created

    def update_alias(self) -> bool:
        new_index = self._cfg.new_index
        if new_index:
            self._create_or_update_alias(alias_name=self._cfg.alias_name, index_name=new_index)
        return bool(new_index)

    def reindex(self) -> None:
        new_index = self._cfg.new_index
        if not new_index:
            _logger.warning("new index not defined.")
            return
        self._reindex(self._cfg.existing_index, new_index)

    def _reindex(self, from_index: str, to_index: str) -> None:
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html
        payload = {"source": {"index": from_index}, "dest": {"index": to_index}}
        _logger.info(f"Reindex docs from {from_index} to {to_index}")
        response = self._client.reindex(  # pylint: disable=unexpected-keyword-arg
            body=payload, wait_for_completion=False
        )
        _logger.info(f"Re-Index Response: {response}")

    @classmethod
    def load_mappings(cls) -> dict:
        mapping_json = pkg_resources.resource_string(__name__, "run_info_es_mapping.json")
        return json.loads(mapping_json)

    def get_current_mapping(self) -> dict:
        index = self._cfg.existing_index
        response = self._client.indices.get_mapping(index=index)
        return response[index]["mappings"]

    def update_mapping(self, new_props) -> dict:
        return self._client.indices.put_mapping(index=self._cfg.existing_index, body=new_props)

    def _create_or_update_alias(self, alias_name: str, index_name: str) -> None:
        if not self._client.indices.exists_alias(name=alias_name):
            _logger.info(f"Created alias {alias_name} for {index_name}")
            self._client.indices.put_alias(index=index_name, name=alias_name)
            return
        alias_data = self._client.indices.get_alias(name=alias_name)
        current_index_alias = list(alias_data)[0]
        _logger.info(f"alias {alias_name} already exists: {alias_data}")
        if current_index_alias == index_name:
            return
        _logger.info(f"update alias {alias_name} for {index_name} (was {current_index_alias})")
        self._client.indices.put_alias(index=index_name, name=alias_name)
        self._client.indices.delete_alias(index=current_index_alias, name=alias_name)

    def _create_index_if_not_exists(self, index_name: str) -> bool:
        if self._client.indices.exists(index=index_name):
            _logger.warning(f"ES Index {index_name} already exists.")
            return False
        # https://opensearch.org/docs/1.2/opensearch/rest-api/index-apis/create-index/
        body = {"mappings": self.load_mappings()}
        response = self._client.indices.create(index=index_name, body=body)
        _logger.info(f"Created index {index_name}: {response}")
        return True
