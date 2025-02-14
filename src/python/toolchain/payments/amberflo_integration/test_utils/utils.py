# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from urllib.parse import parse_qsl

import pkg_resources

AMBERFLO_DOMAIN = "app.amberflo.io"


def load_fixture(fixture_name: str):
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))


def add_create_customer_response(httpx_mock) -> None:
    resp = load_fixture("create_customer_response")
    httpx_mock.add_response(method="POST", url=f"https://{AMBERFLO_DOMAIN}/customer-details", json=resp)


def add_search_customer_response(httpx_mock, search_value: str, is_empty: bool = False) -> None:
    resp = load_fixture("empty_search_customer_response" if is_empty else "search_customer_response")
    httpx_mock.add_response(
        method="GET", url=f"https://{AMBERFLO_DOMAIN}/customers/paging?sort=id&search={search_value}", json=resp
    )


def add_usage_batch_response(httpx_mock, fixture: str) -> None:
    resp = load_fixture(fixture)
    httpx_mock.add_response(method="POST", url=f"https://{AMBERFLO_DOMAIN}/usage/batch", json=resp)


def assert_customer_create_request(request, customer_id: str, customer_name: str) -> None:
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/json"
    assert_amberflo_request(request)
    assert request.url.path == "/customer-details"
    assert json.loads(request.content) == {
        "customerId": customer_id,
        "customerName": customer_name,
    }


def assert_customer_search_request(request, search_value: str) -> None:
    assert request.method == "GET"
    assert_amberflo_request(request)
    assert request.url.path == "/customers/paging"
    assert dict(parse_qsl(request.url.query.decode())) == {"search": search_value, "sort": "id"}


def assert_amberflo_request(request) -> None:
    assert request.headers["X-API-Key"] == "yoyoma"
    assert request.url.scheme == "https"
    assert request.url.host == "app.amberflo.io"


def assert_get_usage_batch_request(request, customer_id: str, start_timestamp: int, end_timestamp: int) -> None:
    assert request.method == "POST"
    assert_amberflo_request(request)
    assert request.url.path == "/usage/batch"
    queries = json.loads(request.read())
    assert queries == [
        {
            "meterApiName": "cache-write-bytes",
            "aggregation": "SUM",
            "filter": {"customerId": customer_id},
            "timeGroupingInterval": "Day",
            "timeRange": {"startTimeInSeconds": start_timestamp, "endTimeInSeconds": end_timestamp},
        },
        {
            "meterApiName": "cache-read-bytes",
            "aggregation": "SUM",
            "filter": {"customerId": customer_id},
            "timeGroupingInterval": "Day",
            "timeRange": {"startTimeInSeconds": start_timestamp, "endTimeInSeconds": end_timestamp},
        },
        {
            "meterApiName": "cache-num-write-blobs",
            "aggregation": "SUM",
            "filter": {"customerId": customer_id},
            "timeGroupingInterval": "Day",
            "timeRange": {"startTimeInSeconds": start_timestamp, "endTimeInSeconds": end_timestamp},
        },
        {
            "meterApiName": "cache-num-read-blobs",
            "aggregation": "SUM",
            "filter": {"customerId": customer_id},
            "timeGroupingInterval": "Day",
            "timeRange": {"startTimeInSeconds": start_timestamp, "endTimeInSeconds": end_timestamp},
        },
    ]
