# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

from toolchain.buildsense.ingestion.run_processors.pants_run_metrics import get_run_metrics
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


def _assert_artifact_dict(artifact_dict: dict) -> None:
    assert artifact_dict == {
        "name": "metrics",
        "description": "Run metrics",
        "artifacts": "aggregate_metrics.json",
        "content_types": ["work_unit_metrics"],
    }


def test_get_run_metrics_witout_counter_names() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    metrics_data = get_run_metrics(build_data, build_data["workunits"])
    assert metrics_data is not None
    metrics_file, artifact_dict = metrics_data
    _assert_artifact_dict(artifact_dict)
    assert metrics_file.name == "aggregate_metrics.json"
    assert metrics_file.content_type == "application/json"
    assert json.loads(metrics_file.content) == [
        {
            "name": "Metrics",
            "content_type": "work_unit_metrics",
            "content": {"local_execution_requests": 2},
        }
    ]


def test_get_run_metrics_with_counters_overlap() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    build_data["counter_names"] = ["local_execution_requests", "shirt"]
    metrics_data = get_run_metrics(build_data, build_data["workunits"])
    assert metrics_data is not None
    metrics_file, artifact_dict = metrics_data
    _assert_artifact_dict(artifact_dict)
    assert metrics_file.name == "aggregate_metrics.json"
    assert metrics_file.content_type == "application/json"
    assert json.loads(metrics_file.content) == [
        {
            "name": "Metrics",
            "content_type": "work_unit_metrics",
            "content": {"local_execution_requests": 2, "shirt": 0},
        }
    ]


def test_get_run_metrics_with_counters() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    build_data["counter_names"] = ["puffy", "shirt"]
    metrics_data = get_run_metrics(build_data, build_data["workunits"])
    assert metrics_data is not None
    metrics_file, artifact_dict = metrics_data
    _assert_artifact_dict(artifact_dict)
    assert metrics_file.name == "aggregate_metrics.json"
    assert metrics_file.content_type == "application/json"
    assert json.loads(metrics_file.content) == [
        {
            "name": "Metrics",
            "content_type": "work_unit_metrics",
            "content": {"local_execution_requests": 2, "shirt": 0, "puffy": 0},
        }
    ]


def test_get_run_metrics_no_metrics() -> None:
    build_data = load_fixture("run_mypy_typecheck")
    assert get_run_metrics(build_data, build_data["workunits"]) is None


def test_get_run_metrics_with_historgram() -> None:
    build_data = load_fixture("run_test_with_metrics_histograms")
    metrics_data = get_run_metrics(build_data, build_data["workunits"])
    assert metrics_data is not None
    metrics_file, artifact_dict = metrics_data
    _assert_artifact_dict(artifact_dict)
    assert metrics_file.name == "aggregate_metrics.json"
    assert metrics_file.content_type == "application/json"
    assert json.loads(metrics_file.content) == [
        {
            "name": "Metrics",
            "content_type": "work_unit_metrics",
            "content": {
                "local_store_read_blob_size_25": 78,
                "local_store_read_blob_size_50": 81,
                "local_store_read_blob_size_75": 84,
                "local_store_read_blob_size_90": 106,
                "local_store_read_blob_size_95": 580,
                "local_store_read_blob_size_99": 4267,
                "local_store_read_blob_size_min": 51,
                "local_store_read_blob_size_max": 88211455,
                "local_store_read_blob_size_mean": 38696.81685346617,
                "local_store_read_blob_size_std_dev": 1797097.6440706071,
                "local_store_read_blob_size_total_observations": 12045,
                "local_store_read_blob_size_sum": 466103159,
                "remote_cache_time_saved_ms_25": 2509,
                "remote_cache_time_saved_ms_50": 3239,
                "remote_cache_time_saved_ms_75": 5727,
                "remote_cache_time_saved_ms_90": 7067,
                "remote_cache_time_saved_ms_95": 7067,
                "remote_cache_time_saved_ms_99": 7883,
                "remote_cache_time_saved_ms_min": 474,
                "remote_cache_time_saved_ms_max": 7883,
                "remote_cache_time_saved_ms_mean": 4067.8571428571427,
                "remote_cache_time_saved_ms_std_dev": 2186.0436166457316,
                "remote_cache_time_saved_ms_total_observations": 14,
                "remote_cache_time_saved_ms_sum": 56950,
                "remote_store_time_to_first_byte_25": 7455,
                "remote_store_time_to_first_byte_50": 9631,
                "remote_store_time_to_first_byte_75": 12271,
                "remote_store_time_to_first_byte_90": 16143,
                "remote_store_time_to_first_byte_95": 17087,
                "remote_store_time_to_first_byte_99": 19439,
                "remote_store_time_to_first_byte_min": 5728,
                "remote_store_time_to_first_byte_max": 19439,
                "remote_store_time_to_first_byte_mean": 10318.324324324325,
                "remote_store_time_to_first_byte_std_dev": 3618.0996509221413,
                "remote_store_time_to_first_byte_total_observations": 37,
                "remote_store_time_to_first_byte_sum": 381778,
                "local_cache_read_errors": 0,
                "local_cache_requests": 14,
                "local_cache_requests_cached": 0,
                "local_cache_requests_uncached": 14,
                "local_cache_total_time_saved_ms": 0,
                "local_cache_write_errors": 0,
                "local_execution_requests": 0,
                "remote_cache_read_errors": 0,
                "remote_cache_requests": 14,
                "remote_cache_requests_cached": 14,
                "remote_cache_requests_uncached": 0,
                "remote_cache_speculation_local_completed_first": 0,
                "remote_cache_speculation_remote_completed_first": 14,
                "remote_cache_total_time_saved_ms": 56945,
                "remote_cache_write_errors": 0,
                "remote_cache_write_finished": 0,
                "remote_cache_write_started": 0,
                "remote_execution_errors": 0,
                "remote_execution_requests": 0,
                "remote_execution_rpc_errors": 0,
                "remote_execution_rpc_execute": 0,
                "remote_execution_rpc_retries": 0,
                "remote_execution_rpc_wait_execution": 0,
                "remote_execution_success": 0,
                "remote_execution_timeouts": 0,
            },
        }
    ]
