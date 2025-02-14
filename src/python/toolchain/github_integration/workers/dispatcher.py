# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.github_integration.workers.configure_repo import GithubRepoConfigurator
from toolchain.github_integration.workers.repo_crawl import GithubRepoStats
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher

_logger = logging.getLogger(__name__)


class GithubIntegrationWorkDispatcher(WorkDispatcher):
    worker_classes = (GithubRepoConfigurator, GithubRepoStats)

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig):
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
