# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging

from toolchain.buildsense.ingestion.run_processors.common import METRICS_FILE_NAME, PipelineResults

_logger = logging.getLogger(__name__)


_REQUIRED_COUNTERS = frozenset(
    [
        "local_cache_requests_cached",
        "remote_cache_requests_cached",
        "local_cache_requests",
        "remote_cache_requests",
        "local_process_total_time_run_ms",
        "remote_process_total_time_run_ms",
        "local_cache_total_time_saved_ms",
        "remote_cache_total_time_saved_ms",
    ]
)


def calculate_indicators(run_id: str, results: PipelineResults) -> dict | None:
    metrics = json.loads(results.get_json_by_name(METRICS_FILE_NAME))[0]["content"]
    if not _REQUIRED_COUNTERS.issubset(metrics.keys()):
        # This is legit since those counters are only available in pants 2.6.1rc0+
        _logger.info(f"Missing counters from metrics {run_id=}")
        return None
    cache_hits_local = metrics["local_cache_requests_cached"]
    cache_hits_remote = metrics["remote_cache_requests_cached"]
    cache_total_local = metrics["local_cache_requests"]
    cache_total_remote = metrics["remote_cache_requests"]
    # NB: If the local cache is enabled, Pants always uses it before the remote cache, and in that
    # case the local cache lookup total represents the overall total. And if we hit locally, we
    # don't look up remotely. So hits are disjoint, but remote lookups are a subset of local
    # lookups.
    #
    # We use `max` here to detect the case where the local cache is disabled, but the remote cache
    # is enabled, which is the only situation where the remote cache would have more accesses than
    # the local cache.
    cache_hits = cache_hits_local + cache_hits_remote
    cache_total = max(cache_total_local, cache_total_remote)
    return {
        "used_cpu_time": metrics["local_process_total_time_run_ms"] + metrics["remote_process_total_time_run_ms"],
        "saved_cpu_time_local": metrics["local_cache_total_time_saved_ms"],
        "saved_cpu_time_remote": metrics["remote_cache_total_time_saved_ms"],
        "saved_cpu_time": metrics["local_cache_total_time_saved_ms"] + metrics["remote_cache_total_time_saved_ms"],
        "hits": cache_hits,
        "total": cache_total,
        "hit_fraction": div_or_zero(cache_hits, cache_total),
        "hit_fraction_local": div_or_zero(cache_hits_local, cache_total_local),
        "hit_fraction_remote": div_or_zero(cache_hits_remote, cache_total_remote),
    }


def div_or_zero(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0
