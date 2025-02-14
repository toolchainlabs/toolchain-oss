# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.dependency.workers.periodic_solutions_remover import OldSolutionRemover, PeriodicSolutionRemover
from toolchain.dependency.workers.resolver_worker import PythonDependenciesResolver
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher

_logger = logging.getLogger(__name__)


class DependencyWorkDispatcher(WorkDispatcher):
    worker_classes = (PeriodicSolutionRemover, OldSolutionRemover, PythonDependenciesResolver)
    sleep_secs = 0.3
    empty_fetch_log_rate = 3000

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> DependencyWorkDispatcher:
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
