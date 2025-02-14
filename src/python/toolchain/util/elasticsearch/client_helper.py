# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from opensearchpy import OpenSearch
from opensearchpy import RequestsHttpConnection as OSRequestsHttpConnection
from opensearchpy.client.utils import _make_path, query_params

from toolchain.aws.auth import get_auth_for_service
from toolchain.util.elasticsearch.config import ElasticSearchConfig


def get_open_search_client(
    es_config: ElasticSearchConfig, aws_region: str | None = None, timeout_in_sec: int | None = None
) -> OpenSearch:
    hosts = es_config.get_es_hosts()
    connection_cls = es_config.connection_cls or OSRequestsHttpConnection
    client_kwargs = dict(
        hosts=hosts, connection_class=connection_cls, max_retries=es_config.max_retries, retry_on_status=(502, 503, 504)
    )
    if es_config.needs_auth:
        awsauth = get_auth_for_service("es", region_name=aws_region)
        client_kwargs.update(http_auth=awsauth, use_ssl=True, verify_certs=True)
    if timeout_in_sec:
        client_kwargs["timeout"] = timeout_in_sec
    return PatchedSearchClient(**client_kwargs)


class PatchedSearchClient(OpenSearch):
    """We override the search method in order to have it use GET instead of POST.

    see: https://github.com/opensearch-project/opensearch-py/issues/95
    """

    @query_params(
        "_source",
        "_source_excludes",
        "_source_includes",
        "allow_no_indices",
        "allow_partial_search_results",
        "analyze_wildcard",
        "analyzer",
        "batched_reduce_size",
        "ccs_minimize_roundtrips",
        "default_operator",
        "df",
        "docvalue_fields",
        "expand_wildcards",
        "explain",
        "from_",
        "ignore_throttled",
        "ignore_unavailable",
        "lenient",
        "max_concurrent_shard_requests",
        "min_compatible_shard_node",
        "pre_filter_shard_size",
        "preference",
        "q",
        "request_cache",
        "rest_total_hits_as_int",
        "routing",
        "scroll",
        "search_type",
        "seq_no_primary_term",
        "size",
        "sort",
        "stats",
        "stored_fields",
        "suggest_field",
        "suggest_mode",
        "suggest_size",
        "suggest_text",
        "terminate_after",
        "timeout",
        "track_scores",
        "track_total_hits",
        "typed_keys",
        "version",
    )
    def search(self, body=None, index=None, params=None, headers=None):
        # from is a reserved word so it cannot be used, use from_ instead
        if "from_" in params:
            params["from"] = params.pop("from_")

        return self.transport.perform_request(
            "GET",
            _make_path(index, "_search"),
            params=params,
            headers=headers,
            body=body,
        )
