# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.users.workers.exporter import PeriodicCustomersExporter, PeriodicRemoteWorkerTokensExporter
from toolchain.users.workers.periodic_access_tokens_checker import (
    PeriodicAccessTokensChecker,
    PeriodicNotifyExpiringTokensExpiration,
    PeriodicTokenRevoker,
)
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher

_logger = logging.getLogger(__name__)


class UsersWorkDispatcher(WorkDispatcher):
    worker_classes = (
        PeriodicAccessTokensChecker,
        PeriodicTokenRevoker,
        PeriodicCustomersExporter,
        PeriodicRemoteWorkerTokensExporter,
        PeriodicNotifyExpiringTokensExpiration,
    )

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig):
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
