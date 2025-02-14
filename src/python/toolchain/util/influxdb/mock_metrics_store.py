# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from unittest import mock
from urllib.parse import ParseResult, parse_qsl, urlparse

from influxdb_client._sync.rest import RESTClientObject

USER_AGENT_EXPRESSION = re.compile(r"influxdb-client-python\/\d+\.\d+\.\d+")


class FakeHTTPResponse(BytesIO):
    status: int
    reason: str
    headers: dict[str, str]

    def __init__(self, status: int, reason: str, json_data: dict | None = None, data: bytes | None = None) -> None:
        if json_data is not None:
            self.data = json.dumps(json_data).encode()
            self.headers = {"Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(self.data))}
        elif data is not None:
            self.data = data
            self.headers = {"Content-Length": str(len(self.data))}
        else:
            self.data = b""
            self.headers = {}

        super().__init__(initial_bytes=self.data)
        self.status = status
        self.reason = reason

    def getheader(self, header: str, default: str | None = None) -> str | None:
        return self.headers.get(header, default)

    def getheaders(self) -> dict[str, str]:
        return self.headers


@dataclass
class Request:
    method: str
    url: str
    body: bytes
    headers: dict[str, str]
    query_params: list[tuple[str, str]]

    def json_body(self) -> dict:
        return json.loads(self.body)


class MockClientFactory:
    def __init__(self, allow_multiple_responses: bool) -> None:
        self._responses: dict[tuple[str, str], list[FakeHTTPResponse | Exception]] = defaultdict(list)
        self._client: MockRestClient | None = None
        self._multiple_responses = allow_multiple_responses

    def __call__(self, configuration, pools_size=4, maxsize=None, retries=False) -> MockRestClient:
        assert self._client is None
        self._client = MockRestClient(
            self.match_response, configuration, pools_size=pools_size, maxsize=maxsize, retries=retries
        )
        self._fake_host = configuration.host
        self.add_write_point_response()
        return self._client

    def _get_client(self) -> MockRestClient:
        assert self._client is not None
        return self._client

    def _get_bucket_json(self, name: str, bucket_id: str | None = None) -> dict:
        bucket_id = bucket_id or uuid.uuid1().hex
        org_id = uuid.uuid1().hex
        return {
            "id": bucket_id,
            "orgID": org_id,
            "type": "user",
            "name": name,
            "retentionRules": [],
            "createdAt": "2021-03-02T19:53:57.21828808Z",
            "updatedAt": "2021-03-02T19:53:57.218288202Z",
            "links": {
                "labels": f"/api/v2/buckets/{bucket_id}/labels",
                "members": f"/api/v2/buckets/{bucket_id}/members",
                "org": f"/api/v2/orgs/{org_id}",
                "owners": f"/api/v2/buckets/{bucket_id}/owners",
                "self": f"/api/v2/buckets/{bucket_id}",
                "write": f"/api/v2/write?org={org_id}&bucket={bucket_id}",
            },
            "labels": [],
        }

    def add_write_point_response(self) -> None:
        self.add_json_response("POST", "/api/v2/write", {})

    def add_ping_response(self) -> None:
        self.add_json_response("GET", "/ping", {})

    def add_missing_bucket_query_response(self, bucket_name: str) -> None:
        self._add_404_response(method="POST", path="/api/v2/query", bucket_name=bucket_name)

    def add_missing_bucket_write_response(self, bucket_name: str) -> None:
        self._add_404_response(method="POST", path="/api/v2/write", bucket_name=bucket_name)

    def _add_404_response(self, method: str, path: str, bucket_name: str) -> None:
        self.add_json_response(
            method=method,
            path=path,
            status=404,
            json_data={
                "code": "not found",
                "message": f'failed to initialize execute state: could not find bucket "{bucket_name}"',
            },
        )

    def add_query_response(self, lines: list[str]) -> None:
        fake_resp = FakeHTTPResponse(status=200, reason="", data="\n".join(lines).encode())
        self._responses[("POST", "/api/v2/query")].append(fake_resp)

    def add_get_buckets_response_with_id(self, bucket_name: str, bucket_id: str) -> None:
        bucket = self._get_bucket_json(bucket_name, bucket_id=bucket_id)
        self.add_json_response("GET", "/api/v2/buckets", {"links": {"self": "TBD"}, "buckets": [bucket]})

    def add_get_buckets_response(self, *bucket_names: str) -> None:
        buckets = [self._get_bucket_json(name) for name in bucket_names]
        self.add_json_response("GET", "/api/v2/buckets", {"links": {"self": "TBD"}, "buckets": buckets})

    def add_get_orgs_response(self) -> None:
        self.add_json_response(
            "GET",
            "/api/v2/orgs",
            {
                "links": {"self": "/api/v2/orgs"},
                "orgs": [
                    {
                        "links": {
                            "buckets": "/api/v2/buckets?org=buildsense",
                            "dashboards": "/api/v2/dashboards?org=buildsense",
                            "labels": "/api/v2/orgs/d73857ea531f4b77/labels",
                            "logs": "/api/v2/orgs/d73857ea531f4b77/logs",
                            "members": "/api/v2/orgs/d73857ea531f4b77/members",
                            "owners": "/api/v2/orgs/d73857ea531f4b77/owners",
                            "secrets": "/api/v2/orgs/d73857ea531f4b77/secrets",
                            "self": "/api/v2/orgs/d73857ea531f4b77",
                            "tasks": "/api/v2/tasks?org=buildsense",
                        },
                        "id": "d73857ea531f4b77",
                        "name": "buildsense",
                        "description": "",
                        "createdAt": "2021-02-22T21:03:15.635655622Z",
                        "updatedAt": "2021-02-22T21:03:15.635655738Z",
                    }
                ],
            },
        )

    def add_create_bucket_response(self, bucket_name: str) -> None:
        self.add_json_response("POST", "/api/v2/buckets", self._get_bucket_json(bucket_name))

    def add_delete_bucket_response(self, bucket_id: str) -> None:
        self.add_json_response("DELETE", f"/api/v2/buckets/{bucket_id}", None)

    def add_update_bucket_response(self, bucket_name: str, bucket_id: str) -> None:
        bucket = self._get_bucket_json(bucket_name, bucket_id=bucket_id)
        self.add_json_response("PATCH", f"/api/v2/buckets/{bucket_id}", bucket)

    def add_json_response(self, method, path, json_data: dict | None, status: int = 200) -> None:
        fake_resp = FakeHTTPResponse(status=status, reason="", json_data=json_data)
        self._responses[(method, path)].append(fake_resp)

    def add_network_error(self, method: str, path: str, error: Exception) -> None:
        self._responses[(method, path)].append(error)

    def match_response(self, method: str, url: str) -> FakeHTTPResponse:
        parsed_url = urlparse(url)
        assert self._fake_host == f"{parsed_url.scheme}://{parsed_url.netloc}"
        responses = self._responses.get((method, parsed_url.path))
        if not responses:
            raise AssertionError(f"No response matched for {method} {url}")
        resp_or_error = responses[0] if self._multiple_responses else responses.pop(0)
        if isinstance(resp_or_error, Exception):
            raise resp_or_error
        return resp_or_error

    def assert_not_used(self) -> None:
        assert self._client is None

    def assert_no_requests(self) -> None:
        assert len(self._get_client().requests) == 0

    def get_request(self) -> Request:
        client = self._get_client()
        assert len(client.requests) == 1
        return client.requests[0]

    def get_requests(self) -> tuple[Request, ...]:
        return tuple(self._get_client().requests)


class FakePoolManager:
    def __init__(self, response_matcher) -> None:
        self._matcher = response_matcher
        self.requests: list[Request] = []

    def request(
        self, method, url, headers=None, body=None, fields=None, preload_content=True, timeout=None, **urlopen_kw
    ):
        if fields:
            query_params = fields
        else:
            parsed_url = urlparse(url)
            query_params = fields or parse_qsl(parsed_url.query)
            url = ParseResult(
                scheme=parsed_url.scheme,
                netloc=parsed_url.netloc,
                path=parsed_url.path,
                params="",
                query="",
                fragment="",
            ).geturl()
        self.requests.append(Request(method=method, url=url, body=body, headers=headers, query_params=query_params))
        return self._matcher(method, url)


class MockRestClient(RESTClientObject):
    def __init__(self, response_matcher, configuration, pools_size=4, maxsize=None, retries=False):
        super().__init__(configuration, pools_size=pools_size, maxsize=maxsize, retries=retries)
        self.pool_manager = FakePoolManager(response_matcher)

    @property
    def requests(self) -> list[Request]:
        return self.pool_manager.requests


def mock_rest_client(allow_multiple_responses: bool = False):
    return mock.patch(
        "influxdb_client._sync.api_client.rest.RESTClientObject", new=MockClientFactory(allow_multiple_responses)
    )


def assert_get_buckets_request(request: Request, bucket_name: str) -> None:
    assert request.body is None
    assert USER_AGENT_EXPRESSION.match(request.headers.pop("User-Agent"))
    assert request.headers == {
        "Accept": "application/json",
        "Authorization": "Token pirate",
        "Content-Type": "application/json",
    }
    assert request.query_params == [("name", bucket_name)]
    assert request.url == "http://jerry.festivus:9911/api/v2/buckets"
    assert request.method == "GET"


def assert_create_bucket_request(request: Request, bucket_name: str, retention_seconds: int = 0) -> None:
    assert USER_AGENT_EXPRESSION.match(request.headers.pop("User-Agent"))
    assert request.headers == {
        "Accept": "application/json",
        "Authorization": "Token pirate",
        "Content-Type": "application/json",
    }
    assert request.url == "http://jerry.festivus:9911/api/v2/buckets"
    assert request.method == "POST"
    expected_rules = [{"type": "expire", "everySeconds": retention_seconds}] if retention_seconds else []
    assert request.json_body() == {
        "orgID": "d73857ea531f4b77",
        "name": bucket_name,
        "retentionRules": expected_rules,
    }


def assert_delete_bucket_request(request: Request, bucket_id: str) -> None:
    assert USER_AGENT_EXPRESSION.match(request.headers.pop("User-Agent"))
    assert request.headers == {
        "Accept": "application/json",
        "Authorization": "Token pirate",
        "Content-Type": "application/json",
    }
    assert request.url == f"http://jerry.festivus:9911/api/v2/buckets/{bucket_id}"
    assert request.method == "DELETE"
    assert request.body is None


def assert_update_bucket_request(request: Request, bucket_name: str, bucket_id: str, retention_seconds: int) -> None:
    assert USER_AGENT_EXPRESSION.match(request.headers.pop("User-Agent"))
    assert request.headers == {
        "Accept": "application/json",
        "Authorization": "Token pirate",
        "Content-Type": "application/json",
    }
    assert request.url == f"http://jerry.festivus:9911/api/v2/buckets/{bucket_id}"
    assert request.method == "PATCH"
    assert request.json_body() == {
        "name": bucket_name,
        "retentionRules": [{"type": "expire", "everySeconds": retention_seconds}],
    }


def assert_write_request(request: Request, org: str, bucket: str) -> list[str]:
    assert request is not None
    assert USER_AGENT_EXPRESSION.match(request.headers.pop("User-Agent"))
    assert request.headers == {
        "Content-Encoding": "identity",
        "Content-Type": "text/plain",
        "Accept": "application/json",
        "Authorization": "Token pirate",
    }
    assert request.query_params == [("org", org), ("bucket", bucket), ("precision", "ns")]
    assert request.url == "http://jerry.festivus:9911/api/v2/write"
    assert request.method == "POST"
    return request.body.decode().splitlines()


def assert_write_requests(requests: Sequence[Request], org: str, bucket: str) -> list[str]:
    lines: list[str] = []
    for req in requests:
        lines.extend(assert_write_request(req, org, bucket))
    return lines
