# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest

from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.util.influxdb.manager import MetricsStoreManager
from toolchain.util.influxdb.mock_metrics_store import (
    assert_create_bucket_request,
    assert_delete_bucket_request,
    assert_get_buckets_request,
    mock_rest_client,
)


@pytest.fixture()
def mock_client():
    with mock_rest_client() as mock_client:
        yield mock_client


@pytest.mark.django_db()
class TestPMetricsStoreManager:
    @pytest.fixture()
    def config(self) -> InfluxDBConnectionConfig:
        return InfluxDBConnectionConfig(org_name="moles", host="jerry.festivus", token="pirate", port=9911)

    def test_init_bucket_exits(self, config: InfluxDBConnectionConfig, mock_client) -> None:
        mgr = MetricsStoreManager(config, bucket_name="mulva")
        mock_client.add_get_buckets_response("mulva")
        assert mgr.init_bucket(recreate=False) is False
        assert_get_buckets_request(mock_client.get_request(), "mulva")

    def test_init_bucket_create(self, config: InfluxDBConnectionConfig, mock_client) -> None:
        mgr = MetricsStoreManager(config, bucket_name="dolores")
        mock_client.add_get_buckets_response()
        mock_client.add_get_orgs_response()
        mock_client.add_create_bucket_response("dolores")
        assert mgr.init_bucket(recreate=False) is True
        requests = mock_client.get_requests()
        assert len(requests) == 3
        assert_get_buckets_request(requests[0], "dolores")
        assert_create_bucket_request(requests[2], "dolores")

    def test_delete_bucket(self, config: InfluxDBConnectionConfig, mock_client) -> None:
        mgr = MetricsStoreManager(config, bucket_name="dolores")
        mock_client.add_get_buckets_response_with_id(bucket_name="dolores", bucket_id="costanza")
        mock_client.add_delete_bucket_response("costanza")
        mgr.delete_bucket()
        requests = mock_client.get_requests()
        assert len(requests) == 2
        assert_get_buckets_request(requests[0], "dolores")
        assert_delete_bucket_request(requests[1], "costanza")
