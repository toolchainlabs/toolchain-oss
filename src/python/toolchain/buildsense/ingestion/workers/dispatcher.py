# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.db.models import QuerySet

from toolchain.buildsense.ingestion.workers.metrics import PantsMetricsConfigurator, PantsMetricsIndexer
from toolchain.buildsense.ingestion.workers.pants_runs import BuilderMover, PantsRunProcessor, QueuedBuildsProcessor
from toolchain.buildsense.ingestion.workers.retention import BuildDataRetention
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher

_logger = logging.getLogger(__name__)


class IngestionWorkDispatcher(WorkDispatcher):
    worker_classes = (
        PantsRunProcessor,
        QueuedBuildsProcessor,
        PantsMetricsIndexer,
        BuildDataRetention,
        PantsMetricsConfigurator,
        BuilderMover,
    )

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> IngestionWorkDispatcher:
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)

    def apply_work_unit_filter(self, queryset: QuerySet) -> QuerySet:
        # In buildsense we want to prioritize processing newer work units,
        # so when we re-run and re-process buildsense data we we always prioritize processing the recently ran builds.
        return queryset.order_by("-id")
