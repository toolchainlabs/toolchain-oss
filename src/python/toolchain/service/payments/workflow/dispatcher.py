# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.payments.amberflo_integration.worker import AmberfloCustomerSyncCreator, PeriodicAmberCustomerSyncer
from toolchain.payments.stripe_integration.worker import PeriodicStripeCustomerSyncer, StripeCustomerSyncCreator
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher


class PaymentsWorkDispatcher(WorkDispatcher):
    worker_classes = (
        PeriodicStripeCustomerSyncer,
        PeriodicAmberCustomerSyncer,
        StripeCustomerSyncCreator,
        AmberfloCustomerSyncCreator,
    )

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> PaymentsWorkDispatcher:
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
