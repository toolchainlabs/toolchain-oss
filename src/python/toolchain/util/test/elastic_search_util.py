# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from queue import Queue

from opensearchpy import RequestsHttpConnection, TransportError
from requests import Timeout

from toolchain.base.toolchain_error import ToolchainAssertion


class NoResponseError(ToolchainAssertion):
    pass


@dataclass(frozen=True)
class Response:
    status_code: int
    headers: dict
    body: bytes

    def get_response_tuple(self):
        return self.status_code, self.headers, self.body.decode()


@dataclass(frozen=True)
class Request:
    method: str
    url: str
    params: dict | None
    headers: dict | None
    body: str | None

    @property
    def key(self) -> tuple[str, str]:
        return self.method, self.url

    def get_json_body(self) -> dict:
        return json.loads(self.body) if self.body else {}


class DummyElasticRequests:
    _instance = None
    _INDEX_NAME = "buildsense"

    @classmethod
    def factory(cls, host: str, port: int, timeout: int = 10) -> DummyElasticRequests:
        return cls._get_instance()

    @classmethod
    def _get_instance(cls) -> DummyElasticRequests:
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance:
            cls._instance._reset()

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._requests: list[Request] = []
        self._responses: dict[tuple[str, str], Queue[Response | TransportError]] = defaultdict(Queue)

    @classmethod
    def get_requests(cls) -> list[Request]:
        return list(cls._get_instance()._requests)

    @classmethod
    def get_request(cls) -> Request:
        reqs = cls.get_requests()
        if len(reqs) != 1:
            raise AssertionError(f"Invalid number of requests: {len(reqs)}")
        return reqs[0]

    @classmethod
    def assert_single_request(cls) -> None:
        reqs = cls.get_requests()
        if len(reqs) != 1:
            raise AssertionError(f"Invalid number of requests: {len(reqs)}")

    @classmethod
    def assert_no_requests(cls) -> None:
        reqs = cls.get_requests()
        if reqs:
            raise AssertionError(f"Requests were made: {reqs}")

    @classmethod
    def _generate_hits(cls, index, run_infos) -> list[dict]:
        docs = []
        for run_info in run_infos:
            docs.append(
                {
                    # Our ES code don't care about the document id when reading data.
                    "_index": index,
                    "_type": "run_info",
                    "_score": 1.0,
                    "_id": str(uuid.uuid4),
                    "sort": [
                        run_info.timestamp.timestamp(),
                        run_info.server_info.accept_time.timestamp(),
                        "fake-doc-id",  # This can be fake because we don't use it w/ cursor logic
                    ],
                    "_source": {
                        "customer_id": run_info.customer_id,
                        "repo_id": run_info.repo_id,
                        "user_api_id": run_info.user_api_id,
                        "run_id": run_info.run_id,
                    },
                }
            )
        return docs

    @classmethod
    def _generate_aggregation_response(cls, results: tuple[tuple[str, Sequence[str | int]], ...]) -> dict:
        aggregations = {}
        for name, buckets in results:
            aggregations[name] = {
                "doc_count_error_upper_bound": 0,
                "sum_other_doc_count": 0,
                "buckets": [{"key": bucket, "doc_count": 21} for bucket in buckets],
            }
        return {
            "took": 12,
            "timed_out": False,
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 3420, "relation": "eq"}, "max_score": None, "hits": []},
            "aggregations": aggregations,
        }

    @classmethod
    def _get_suggest_option(cls, value: str) -> dict:
        return {
            "text": value,
            "_index": cls._INDEX_NAME,
            "_type": "run_info",
            "_id": "no-soup-for-you",
            "_score": 1.0,
            "_source": {"title": "Add PR title to PullRequestInfo (#8741)"},
        }

    @classmethod
    def add_has_documents_response(cls, index: str, docs_count: int) -> None:
        cls.add_response(
            "GET",
            f"/{index}/_search",
            json_body={
                "took": 33,
                "timed_out": False,
                "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
                "hits": {"total": {"value": docs_count, "relation": "eq"}, "max_score": None, "hits": []},
            },
        )

    @classmethod
    def add_suggest_response(cls, suggest_name: str, values) -> None:
        options = [cls._get_suggest_option(value) for value in values]
        json_body = {
            "suggest": {suggest_name: [{"text": "something", "offset": 0, "length": len(values), "options": options}]}
        }
        cls.add_response("GET", "/buildsense/_search", json_body=json_body)

    @classmethod
    def add_aggregation_response(cls, index: str, results: tuple[tuple[str, Sequence[str | int]], ...]) -> None:
        response = cls._generate_aggregation_response(results)
        cls.add_response("GET", f"/{index}/_search", json_body=response)

    @classmethod
    def add_search_response(cls, run_infos, override_total=None) -> None:
        hits = cls._generate_hits(cls._INDEX_NAME, run_infos)
        cls._add_search_response(cls._INDEX_NAME, hits=hits, override_total=override_total)

    @classmethod
    def add_empty_search_response(cls) -> None:
        cls._add_search_response(cls._INDEX_NAME, hits=[], override_total=None)

    @classmethod
    def _add_search_response(cls, index: str, hits: list[dict], override_total: int | None) -> None:
        total_hits = len(hits) if override_total is None else override_total
        search_resp = {
            "took": 4,
            "timed_out": False,
            "hits": {
                # We allow overriding the total value so we can assert that it gets properly returned from
                # the logic calling ES (as opposed to returning the number of hits)
                # The ES Behavior is to return a page of results and a number indicating the total number of
                # results across the entire index.
                "total": {"value": total_hits, "relation": "eq"},
                "max_score": 1.0,
                "hits": hits,
            },
        }
        cls.add_response("GET", f"/{index}/_search", json_body=search_resp)

    @classmethod
    def add_response(
        cls,
        method: str,
        url: str,
        status_code: int = 200,
        body: str | bytes = "",
        json_body: dict | None = None,
    ) -> None:
        if json_body is not None:
            body = json.dumps(json_body)
        if not isinstance(body, bytes):
            body = body.encode()
        cls._get_instance()._responses[(method, url)].put_nowait(
            Response(status_code=status_code, headers={}, body=body)
        )

    @classmethod
    def add_search_network_error(cls, error_cls: type[TransportError], error_msg: str) -> None:
        transport_error = Timeout("They are running out of shrimp")
        error = error_cls("The ocean called.", str(transport_error), transport_error)
        cls.add_error_response("GET", f"/{cls._INDEX_NAME}/_search", error)

    @classmethod
    def add_search_http_error_response(cls, http_error_code: int, error_msg: str) -> None:
        cls.add_response(
            "GET", f"/{cls._INDEX_NAME}/_search", status_code=http_error_code, json_body={"message": error_msg}
        )

    @classmethod
    def add_error_response(cls, method: str, url: str, error: TransportError) -> None:
        cls._get_instance()._responses[(method, url)].put_nowait(error)

    def perform_request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        body: str | None = None,
        timeout: int | None = None,
        ignore=(),
        headers: dict | None = None,
    ):
        req = Request(method=method, url=url, params=params, headers=headers, body=body)
        self._requests.append(req)
        queue = self._responses[req.key]
        if not queue.qsize():
            raise NoResponseError(f"No response for {method} {url}")
        response_or_error = queue.get_nowait()
        if not isinstance(response_or_error, Response):
            raise response_or_error
        status_code = response_or_error.status_code
        if not (200 <= status_code < 300) and status_code not in ignore:
            # Logic similar to RequestsHttpConnection.perform_request()
            raw_data = response_or_error.body.decode("utf-8", "surrogatepass")
            content_type = response_or_error.headers.get("Content-Type")
            RequestsHttpConnection()._raise_error(status_code, raw_data=raw_data, content_type=content_type)
        return response_or_error.get_response_tuple()
