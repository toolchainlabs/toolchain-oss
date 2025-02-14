# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from collections.abc import Iterable, Iterator

from hdrh.histogram import HdrHistogram

from toolchain.buildsense.ingestion.run_processors.common import METRICS_FILE_NAME, FileInfo, RunArtifact

logger = logging.getLogger(__name__)

_CONTENT_TYPE = "work_unit_metrics"
_HIST_PERCENTILES = (25, 50, 75, 90, 95, 99)


def get_run_metrics(build_data: dict, work_units: Iterable[dict]) -> RunArtifact:
    counter_names = build_data.get("counter_names", [])
    work_unit_metrics = aggregate_work_unit_metrics(counter_names, work_units)
    histograms = _get_histograms_metrics(build_data)
    if not work_unit_metrics and not histograms:
        return None
    metrics = histograms
    metrics.update(work_unit_metrics)

    artifact = [
        {
            "name": "Metrics",
            "content_type": _CONTENT_TYPE,
            "content": metrics,
        }
    ]
    metrics_file = FileInfo.create_json_file(METRICS_FILE_NAME, artifact)
    return metrics_file, {
        "name": "metrics",
        "description": "Run metrics",
        "artifacts": metrics_file.name,
        "content_types": [_CONTENT_TYPE],
    }


def aggregate_work_unit_metrics(counter_names: list[str], work_units: Iterable[dict]) -> dict[str, int]:
    counters: dict[str, int] = defaultdict(int, [(name, 0) for name in counter_names])
    for wu_counters in _iter_counters(work_units):
        for key, value in wu_counters.items():
            counters[key] += value
    return OrderedDict(sorted(counters.items()))


def _iter_counters(work_units: Iterable[dict]) -> Iterator[dict[str, int]]:
    for wu in work_units:
        counters = wu.get("counters")
        if counters:
            yield counters


def _get_histograms_metrics(build_data: dict) -> dict[str, int]:
    metrics: dict[str, int] = {}
    if "observation_histograms" not in build_data:
        return metrics
    histograms = build_data["observation_histograms"]["histograms"]
    # for name, encoded_historgram in histograms.items():
    for name, encoded_historgram in histograms.items():
        histogram = HdrHistogram.decode(encoded_historgram)
        percentiles = histogram.get_percentile_to_value_dict(_HIST_PERCENTILES)
        metrics.update({f"{name}_{percentile}": value for percentile, value in percentiles.items()})
        metrics.update(
            {
                f"{name}_min": histogram.get_min_value(),
                f"{name}_max": histogram.get_max_value(),
                f"{name}_mean": histogram.get_mean_value(),
                f"{name}_std_dev": histogram.get_stddev(),
                f"{name}_total_observations": histogram.total_count,
                f"{name}_sum": int(histogram.get_mean_value() * histogram.total_count),
            }
        )
    return metrics
