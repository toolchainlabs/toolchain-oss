# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import httpx
import pytest

from toolchain.util.net.httpx_util import get_http_retry_client


class TestHttpErrorRetryClient:
    def test_http_ok(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url="http://newman.local/chicken/", json={"msg": "ok"})
        client = get_http_retry_client(
            base_url="http://newman.local/", service_name="jerry", timeout=2, transport_retries=2, http_error_retries=3
        )
        response = client.get("chicken/")
        assert response.status_code == 200
        assert response.json() == {"msg": "ok"}

    def test_network_error(self, httpx_mock) -> None:
        httpx_mock.add_exception(httpx.ReadTimeout("no soup for you"), method="GET", url="http://newman.local/kenny/")
        client = get_http_retry_client(
            base_url="http://newman.local/", service_name="jerry", timeout=2, transport_retries=2, http_error_retries=3
        )
        with pytest.raises(httpx.ReadTimeout, match="no soup for you"):
            client.get("kenny/")

    def test_http_500_error(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url="http://newman.local/chicken/", status_code=500, json={"msg": "bob"})
        client = get_http_retry_client(
            base_url="http://newman.local/", service_name="jerry", timeout=2, transport_retries=2, http_error_retries=3
        )
        response = client.get("chicken/")
        assert response.status_code == 500
        assert response.json() == {"msg": "bob"}
        assert len(httpx_mock.get_requests()) == 1

    def test_http_503_non_transient_error(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url="http://newman.local/chicken/", status_code=503, json={"msg": "bob"})
        client = get_http_retry_client(
            base_url="http://newman.local/", service_name="jerry", timeout=2, transport_retries=2, http_error_retries=3
        )
        response = client.get("chicken/")
        assert response.status_code == 503
        assert response.json() == {"msg": "bob"}
        assert len(httpx_mock.get_requests()) == 1

    def test_http_transient_error_all_failed(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url="http://newman.local/rogers/",
            status_code=503,
            json={"error": "transient", "error_type": "OperationalError"},
        )
        client = get_http_retry_client(
            base_url="http://newman.local/", service_name="jerry", timeout=2, transport_retries=2, http_error_retries=3
        )
        response = client.get("rogers/")
        assert response.status_code == 503
        assert response.json() == {"error": "transient", "error_type": "OperationalError"}
        assert len(httpx_mock.get_requests()) == 3

    def test_http_transient_error_retry_success(self, httpx_mock, caplog) -> None:
        httpx_mock.add_response(
            method="GET",
            url="http://newman.local/rogers/",
            status_code=503,
            json={"error": "transient", "error_type": "OperationalError"},
        )
        httpx_mock.add_response(method="GET", url="http://newman.local/rogers/", json={"msg": "I was in a pool"})
        client = get_http_retry_client(
            base_url="http://newman.local/", service_name="jerry", timeout=2, transport_retries=2, http_error_retries=15
        )
        response = client.get("rogers/")
        assert response.status_code == 200
        assert response.json() == {"msg": "I was in a pool"}
        assert len(httpx_mock.get_requests()) == 2
        assert len(caplog.records) == 1
        assert (
            caplog.records[0].message
            == "transient_error: service=jerry url=http://newman.local/rogers/ method=GET retries_left=14 error_type='OperationalError' status=503"
        )
