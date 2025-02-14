# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from prometheus_client.core import REGISTRY, GaugeMetricFamily
from prometheus_client.registry import Collector

from toolchain.workflow.models import WorkUnitStateCount

_logger = logging.getLogger(__name__)


class WorkflowQueuesCollector(Collector):
    def collect(self):
        count_by_model = WorkUnitStateCount.get_counts_by_model_and_state()
        metric = GaugeMetricFamily(
            "toolchain_workflow_workunit_state",
            "Number of work units by payload type and state",
            labels=("payload_model", "state"),
        )
        for model, counts_by_state in count_by_model.items():
            for state, count in counts_by_state.items():
                metric.add_metric(value=count, labels=(model, state))
        yield metric


def add_queues_collector() -> None:
    # forces a django backend load/init here. since calling REGISTRY.register takes a lock,
    # then calling WorkUnitStateCount.get_counts_by_model_and_state() will trirgger an django init
    # which also initlizes jango_prometheus which will try to get the lock again and cause a dead-lock
    payload_models_names = tuple(WorkUnitStateCount.get_counts_by_model_and_state().keys())
    _logger.info(f"aadd workflow queue collecter for models: {payload_models_names}")
    REGISTRY.register(WorkflowQueuesCollector())
