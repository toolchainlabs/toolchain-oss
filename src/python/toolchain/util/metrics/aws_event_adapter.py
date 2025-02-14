# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from threading import current_thread

from prometheus_client import Histogram

from toolchain.aws.aws_api import AWSService

_logger = logging.getLogger(__name__)


class PrometheusAwsMetricsAdapter:
    @classmethod
    def add_labels(cls, *label_names: str) -> list[str]:
        all_labels = ["operation"]
        all_labels.extend(label_names)
        return all_labels

    @classmethod
    @contextmanager
    def track_latency(cls, aws_client: AWSService, histogram: Histogram, **labels) -> Iterator:
        event_system = aws_client.client.meta.events
        client_id = f"{aws_client.service}_{id(aws_client.client)}"
        adapter = cls(client_id, histogram, event_system, labels)
        try:
            adapter.register()
            yield
        finally:
            adapter.unregister()

    def __init__(self, client_id, histogram, event_system, labels: dict[str, str]) -> None:
        self._histogram = histogram
        self._client_id = client_id
        self._labels = labels
        self._start: float | None = None
        self._es = event_system
        self._thread_id = current_thread().ident

    def register(self) -> None:
        self._es.register("before-call", self._before_handler)
        self._es.register("after-call", self._after_handler)

    def unregister(self) -> None:
        self._es.unregister("before-call", self._before_handler)
        self._es.unregister("after-call", self._after_handler)

    @property
    def _is_same_thread(self) -> bool:
        return self._thread_id == current_thread().ident

    def _before_handler(self, model, **kwargs):
        if not self._is_same_thread:
            return
        if self._start is not None:
            _logger.warning(
                f"before_handler before after_handler {id(self)} client={self._client_id} {model.service_model.service_name}/{model.name}, igoring."
            )
            return
        self._start = time.time()

    def _after_handler(self, model, **kwargs):
        if not self._is_same_thread:
            return
        start = self._start
        self._start = None
        if start is None:
            _logger.warning(
                f"after_handler called before 'before_handler' {id(self)} client={self._client_id} {model.service_model.service_name}/{model.name}, igoring."
            )
            return
        self._histogram.labels(operation=model.name, **self._labels).observe(time.time() - start)
