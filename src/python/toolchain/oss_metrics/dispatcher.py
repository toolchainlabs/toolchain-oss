# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.oss_metrics.bugout_integration.workers import BugoutDayDataDownloader
from toolchain.oss_metrics.workers import (
    AnonymouseTelemetryProcessingScheduler,
    GithubRepoStatsUpsertScheduler,
    GithubStatsDataLoader,
    PantsTelemetryDataLoader,
)
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher


class OssMetricsWorkflowDispatcher(WorkDispatcher):
    worker_classes = (
        AnonymouseTelemetryProcessingScheduler,
        BugoutDayDataDownloader,
        PantsTelemetryDataLoader,
        GithubStatsDataLoader,
        GithubRepoStatsUpsertScheduler,
    )

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> OssMetricsWorkflowDispatcher:
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
