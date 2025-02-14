# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import logging

from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher, WorkerClasses

logger = logging.getLogger(__name__)


class CrawlerWorkDispatcher(WorkDispatcher, metaclass=abc.ABCMeta):
    """A workflow dispatcher that performs crawl work."""

    @classmethod
    @abc.abstractmethod
    def get_all_worker_classes(cls) -> WorkerClasses:
        """Subclasses must return a list of all worker types that can perform work for this crawler."""

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> CrawlerWorkDispatcher:
        worker_classes = config.extrapolate_worker_classes(cls.get_all_worker_classes())
        return cls.for_worker_classes(config=config, worker_classes=worker_classes)
