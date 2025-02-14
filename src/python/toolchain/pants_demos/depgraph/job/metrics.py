# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import CollectorRegistry, Histogram, push_to_gateway


class Metrics:
    _PREFIX = "toolchain_pants_demo_depgraph_"
    _LATENCY_BUCKETS = (
        1,
        3,
        5,
        8,
        10,
        20,
        30,
        40,
        50,
        60,
        70,
        80,
        90,
        120,
        180,
        220,
        300,
        400,
        500,
        600,
        800,
        900,
        1200,
        2000,
        3000,
        float("inf"),
    )

    def __init__(self, *, push_gateway_url: str | None) -> None:
        self._push_gateway_url = push_gateway_url
        self._registry = CollectorRegistry()
        self._clone_latency = Histogram(
            name=self._PREFIX + "clone_latency",
            documentation="Histogram repo clone latency.",
            registry=self._registry,
            buckets=self._LATENCY_BUCKETS,
        )
        self._pants_command_latency = Histogram(
            name=self._PREFIX + "pants_latency",
            documentation="Histogram pants commands latency.",
            labelnames=("goal",),
            registry=self._registry,
            buckets=self._LATENCY_BUCKETS,
        )

    @contextmanager
    def track_clone_latency(self) -> Iterator[Metrics]:
        with self._clone_latency.time():
            yield self

    @contextmanager
    def track_pants_latency(self, goal: str) -> Iterator[Metrics]:
        with self._pants_command_latency.labels(goal=goal).time():
            yield self

    def report_metrics(self) -> None:
        if not self._push_gateway_url:
            return
        push_to_gateway(self._push_gateway_url, job="pants_demo_depgraph", registry=self._registry)
