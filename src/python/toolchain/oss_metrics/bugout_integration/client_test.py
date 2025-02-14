# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from textwrap import dedent
from urllib.parse import parse_qs, urlparse

import pytest
from faker import Faker

from toolchain.oss_metrics.bugout_integration.client import BugoutClient, TransientBugoutError

BUGOUT_GATEWAY_TIMEOUT = dedent(
    """<html>
    <head><title>504 Gateway Time-out</title></head>
    <body>
    <center><h1>504 Gateway Time-out</h1></center>
    <hr><center>nginx</center>
    </body>
    </html>
"""
)


def add_bugout_http_504_error_response(responses):
    responses.add(
        responses.GET, "https://spire.bugout.dev/journals/shmoopi/search", status=504, body=BUGOUT_GATEWAY_TIMEOUT
    )


def add_bugout_search_response(responses, entries_count: int = 0, next_offset: int | None = None) -> None:
    fk = Faker()

    def _get_fake_result():
        return {
            "entry_url": fk.uri(),
            "content_url": fk.uri(),
            "title": fk.sentence(),
            "tags": fk.words(),
            "created_at": fk.iso8601(),
            "updated_at": fk.iso8601(),
            "score": fk.pyfloat(2),
        }

    json_payload = {
        "total_results": 0,
        "offset": 0,
        "max_score": 0,
        "results": [_get_fake_result() for _ in range(entries_count)],
    }
    if next_offset:
        json_payload["next_offset"] = next_offset
    responses.add(responses.GET, "https://spire.bugout.dev/journals/shmoopi/search", json=json_payload)


def assert_bugout_request(
    request, offset: int | None = None, from_ts: int = 1640995200, to_ts: int = 1641168000
) -> None:
    assert request.method == "GET"
    assert request.headers["Authorization"] == "Bearer summer of george"
    url = urlparse(request.url)
    assert url.scheme == "https"
    assert url.netloc == "spire.bugout.dev"
    assert url.path == "/journals/shmoopi/search"
    assert parse_qs(url.query) == {
        "q": ["order=asc"],
        "filters": [f"created_at:>={from_ts}", f"created_at:<{to_ts}"],
        "limit": ["500"],
        "offset": [str(offset)] if offset else ["0"],
        "content": ["True"],
        "order": ["desc"],
    }


class TestBugoutClient:
    @pytest.fixture()
    def bugout_client(self) -> BugoutClient:
        return BugoutClient.for_django_settings(journal_id="shmoopi")

    def test_get_entries_no_data(self, responses, bugout_client: BugoutClient) -> None:
        add_bugout_search_response(responses)
        entries = bugout_client.get_entries(
            from_datetime=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            to_datetime=datetime.datetime(2022, 1, 3, tzinfo=datetime.timezone.utc),
        )
        assert len(entries) == 0
        assert len(responses.calls) == 1
        assert_bugout_request(responses.calls[0].request)

    def test_get_entries_single_page(self, responses, bugout_client: BugoutClient) -> None:
        add_bugout_search_response(responses, 9)
        entries = bugout_client.get_entries(
            from_datetime=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            to_datetime=datetime.datetime(2022, 1, 3, tzinfo=datetime.timezone.utc),
        )
        assert len(entries) == 9
        assert len(responses.calls) == 1
        assert_bugout_request(responses.calls[0].request)

    def test_get_entries_multi_page(self, responses, bugout_client: BugoutClient) -> None:
        add_bugout_search_response(responses, 20, next_offset=90)
        add_bugout_search_response(responses, 8)
        entries = bugout_client.get_entries(
            from_datetime=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            to_datetime=datetime.datetime(2022, 1, 3, tzinfo=datetime.timezone.utc),
        )
        assert len(entries) == 28
        assert len(responses.calls) == 2
        assert_bugout_request(responses.calls[0].request)
        assert_bugout_request(responses.calls[1].request, offset=90)

    def test_get_entries_http_504(self, responses, bugout_client: BugoutClient) -> None:
        add_bugout_http_504_error_response(responses)
        with pytest.raises(TransientBugoutError, match=r"BugoutResponseException.*Network error"):
            bugout_client.get_entries(
                from_datetime=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
                to_datetime=datetime.datetime(2022, 1, 3, tzinfo=datetime.timezone.utc),
            )
        assert len(responses.calls) == 1
        assert_bugout_request(responses.calls[0].request)
