# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import os
import time

import httpx
import ndjson
import sentry_sdk

from toolchain.aws.auth import get_auth_for_service
from toolchain.aws.dynamodb import ValuesConverter
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.records.adapters import from_dynamodb_item, to_elasticsearch_document
from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig

_logger = logging.getLogger(__name__)


class BuildDataDynamoDB2ElasticSearch:
    # in seconds
    _OPENSEARCH_CHECK_TIMEOUT = 1
    _OPENSEARCH_BULK_TIMEOUT_BASE = 3

    def __init__(self, region_name: str, opensearch_config: BuildSenseElasticSearchConfig) -> None:
        self._region = region_name
        self._indices = opensearch_config.indices_names
        self._converter = ValuesConverter()
        auth = get_auth_for_service(aws_service="es", region_name=self._region)
        self._client = httpx.Client(base_url=f"https://{opensearch_config.host}/", auth=auth)

    def _get_es_docs(self, records: list[dict]) -> dict[str, dict | None]:
        docs_map = {}
        for record in records:
            dynamodb_data = record["dynamodb"]
            keys = self._converter.parse_record(dynamodb_data["Keys"])
            document_id = f'{keys["EnvCustomerRepoUser"]}:{keys["run_id"]}'
            is_remove = record["eventName"] == "REMOVE"
            run_info_json = None
            if not is_remove:
                run_info = from_dynamodb_item(self._converter.parse_record(record["dynamodb"]["NewImage"]))
                run_info_json = to_elasticsearch_document(run_info)
            docs_map[document_id] = run_info_json
        return docs_map

    def _to_actions(self, docs_map: dict[str, dict | None]) -> list[dict]:
        remove_count = 0
        update_count = 0
        actions = []
        for doc_id, doc in docs_map.items():
            is_remove = doc is None
            action = "delete" if is_remove else "index"
            for index_name in self._indices:
                actions.append({action: {"_index": index_name, "_id": doc_id}})
                if doc is None:  # is_remove, using doc here to make mypy happy.
                    remove_count += 1
                else:
                    update_count += 1
                    actions.append(doc)
        _logger.info(
            f"es_actions: removes={remove_count} updates={update_count} total={len(docs_map)} rows={len(actions)} indices={self._indices}"
        )
        return actions

    def check_es_connection(self) -> str:
        resp = self._client.get(url="", timeout=self._OPENSEARCH_CHECK_TIMEOUT)
        _logger.info(f"OpenSearch Response: {resp} {resp.text}")
        resp.raise_for_status()
        return resp.text

    def raise_for_sentry_check(self) -> None:
        raise ToolchainAssertion("Dummy error, testing sentry integration.")

    def bulk_process_records(self, records: list[dict]) -> tuple[int, int, dict]:
        docs_map = self._get_es_docs(records)
        actions = self._to_actions(docs_map)
        request_data = (ndjson.dumps(actions) + "\n").encode()
        start = time.time()
        timeout = self._OPENSEARCH_BULK_TIMEOUT_BASE * (
            int(len(records) / 1000) + 1
        )  # timeout based on the number of docs we bulk upload.
        try:
            resp = self._client.post(
                url="_bulk",
                content=request_data,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=timeout,
            )
        except httpx.RequestError:
            latency = time.time() - start
            _logger.error(
                f"Request Network error error. latency={latency} {timeout=} actions={len(actions)} data_size={len(request_data)}"
            )
            raise
        latency = time.time() - start
        if not resp.is_error:
            resp_json = resp.json()
            took = resp_json["took"]
            errors = resp_json["errors"]
            items = len(resp_json["items"])
            _logger.info(
                f"Updated ES Index: {latency=} {timeout=} {took=}msec {errors=} {items=} records={len(records)} data_size={len(request_data)}"
            )
        else:
            _logger.error(f"HTTP Request error. latency={latency} status_code={resp.status_code} {resp.text}")
        resp.raise_for_status()
        return len(actions), resp.status_code, resp.json()


def _config_logging(request_id: str) -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
    logging.basicConfig(format=f"{request_id} [%(asctime)s %(levelname)s] %(message)s", level=logging.INFO)


def handler(event, context) -> str | None:
    region = os.environ.get("REGION_NAME", "us-east-1")
    sentry_dsn = os.environ.get("SENTRY_DSN")
    es_host = os.environ.get("ES_HOST")
    if not sentry_dsn:
        print("ERROR: no SENTRY_DSN not set")
        raise ToolchainAssertion("SENTRY_DSN not set")
    if not es_host:
        print("ES_HOST not set")
        raise ToolchainAssertion("ES_HOST not set in env")
    sentry_sdk.init(sentry_dsn, environment="ddb_to_es_lambda")
    request_id = context.aws_request_id
    try:
        _config_logging(request_id)
        es_cfg = BuildSenseElasticSearchConfig.for_lambda(es_host=es_host)
        pusher = BuildDataDynamoDB2ElasticSearch(region, es_cfg)
        internal_check = event.get("CHECKS")
        if internal_check == "ES":
            return pusher.check_es_connection()
        elif internal_check == "SENTRY":
            pusher.raise_for_sentry_check()
            return None
        pusher.bulk_process_records(event["Records"])
        return None
    except Exception as error:
        sentry_sdk.capture_exception(error)
        sentry_sdk.flush(timeout=3)
        raise
