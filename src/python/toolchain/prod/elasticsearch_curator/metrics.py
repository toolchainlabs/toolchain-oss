# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from contextlib import contextmanager

from prometheus_client import CollectorRegistry, Gauge, Histogram, push_to_gateway

from toolchain.util.config.kubernetes_env import KubernetesEnv


class Metrics:
    _PREFIX = "toolchain_logs_curator_"

    def __init__(self, *, push_gateway_url: str, dry_run: bool, k8s_env: KubernetesEnv):
        self._push_gateway_url = push_gateway_url
        self._registry = CollectorRegistry()
        self._labels_values = {
            "dry_run": "1" if dry_run else "0",
            "pod": k8s_env.pod_name,
            "namespace": k8s_env.namespace,
        }
        labels = list(self._labels_values.keys())
        self._run_time = Histogram(
            name=self._PREFIX + "job_latency",
            documentation="Histogram job run time.",
            registry=self._registry,
            labelnames=labels,
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 90.0, 120.0, 300.0, float("inf")),
        )
        self._indices_removed = Gauge(
            name=self._PREFIX + "indices_removed",
            documentation="Number of indices removed",
            registry=self._registry,
            labelnames=labels,
        )

    def measure_indices_removed(self, indices_removed: int) -> None:
        self._indices_removed.labels(**self._labels_values).set(indices_removed)

    @contextmanager
    def track(self):
        with self._run_time.labels(**self._labels_values).time():
            yield self

        if self._push_gateway_url:
            push_to_gateway(self._push_gateway_url, job="logs_curator", registry=self._registry)
