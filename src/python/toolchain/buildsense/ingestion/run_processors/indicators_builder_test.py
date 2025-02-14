# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.buildsense.ingestion.run_processors.artifacts_test import create_run_info
from toolchain.buildsense.ingestion.run_processors.common import FileInfo, PipelineResults
from toolchain.buildsense.ingestion.run_processors.indicators_builder import calculate_indicators
from toolchain.buildsense.ingestion.run_processors.pants_run_metrics import get_run_metrics
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


def test_calculate_indicators() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")

    run_info = create_run_info(build_data, stats_version="3")
    metrics_file = FileInfo.create_json_file("aggregate_metrics", load_fixture("typecheck_run_aggregated_metrics"))
    results = PipelineResults(run_info=run_info, files=(metrics_file,), has_metrics=True)
    indicators = calculate_indicators(run_id=run_info.run_id, results=results)
    assert indicators == {
        "used_cpu_time": 160429,
        "saved_cpu_time": 373895,
        "saved_cpu_time_local": 370884,
        "saved_cpu_time_remote": 3011,
        "hits": 1103,
        "total": 1135,
        "hit_fraction": 0.9718061674008811,
        "hit_fraction_local": 0.9577092511013215,
        "hit_fraction_remote": 0.37209302325581395,
    }


def test_calculate_indicators_with_zeros() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    run_info = create_run_info(build_data, stats_version="3")
    metrics = load_fixture("typecheck_run_aggregated_metrics")
    metrics[0]["content"].update(remote_cache_requests=0, remote_cache_total_time_saved_ms=0)  # type: ignore[index]
    metrics_file = FileInfo.create_json_file("aggregate_metrics", metrics)
    results = PipelineResults(run_info=run_info, files=(metrics_file,), has_metrics=True)
    indicators = calculate_indicators(run_id=run_info.run_id, results=results)
    assert indicators == {
        "used_cpu_time": 160429,
        "saved_cpu_time": 370884,
        "saved_cpu_time_local": 370884,
        "saved_cpu_time_remote": 0,
        "hits": 1103,
        "total": 1135,
        "hit_fraction": 0.9718061674008811,
        "hit_fraction_local": 0.9577092511013215,
        "hit_fraction_remote": 0,
    }


def test_calculate_indicators_missing_counters() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    run_info = create_run_info(build_data, stats_version="3")
    metrics_result = get_run_metrics(build_data, build_data["workunits"])
    assert metrics_result is not None
    results = PipelineResults(run_info=run_info, files=(metrics_result[0],), has_metrics=True)
    assert calculate_indicators(run_id=run_info.run_id, results=results) is None
