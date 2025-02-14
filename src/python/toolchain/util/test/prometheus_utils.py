# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from prometheus_client import REGISTRY


def assert_latest_metric_equals(metric_name: str, expected_value: int | float):
    last_sample = _get_metric(metric_name).samples[0]
    assert last_sample.value == expected_value  # nosec: B101


def _get_metric(metric_name: str):
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample[0] == metric_name:
                return metric
    return None
